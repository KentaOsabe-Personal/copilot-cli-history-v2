from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.types import (
    NormalizedEvent,
    NormalizedSession,
    ReadFailureResult,
    ReadIssue,
    ReadSuccessResult,
    ResolvedHistoryRoot,
)
from history_api.services import HistoryApiService, detail_payload_for_response
from history_read_model.fake_repository import FakeBigQueryReadModelRepository
from history_read_model.repository import (
    RepositoryError,
    RepositoryExecutionOptions,
    SessionDetailResult,
    SessionListCriteria,
    SessionListResult,
    SyncRunLookupResult,
    SyncRunResult,
    SyncRunStartResult,
    SyncWriteResult,
)
from tests.history_api.fakes import build_history_api_test_repository


def _criteria(*, search_term: str | None = None) -> SessionListCriteria:
    return SessionListCriteria(
        from_datetime=datetime(2026, 6, 9, 0, tzinfo=UTC),
        to_datetime=datetime(2026, 6, 10, 0, tzinfo=UTC),
        search_term=search_term,
        limit=None,
    )


def _event() -> NormalizedEvent:
    return NormalizedEvent(
        sequence=1,
        kind="message",
        mapping_status="complete",
        raw_type="user.message",
        occurred_at=datetime(2026, 6, 9, 10, tzinfo=UTC),
        role="user",
        content="hello",
        tool_calls=(),
        detail={},
        raw_payload={"type": "user.message"},
    )


def _session(
    session_id: str,
    *,
    source_state: str = "complete",
    issues: tuple[ReadIssue, ...] = (),
) -> NormalizedSession:
    return NormalizedSession(
        session_id=session_id,
        source_format="current",
        source_state=source_state,  # type: ignore[arg-type]
        cwd="/workspace",
        git_root="/workspace",
        repository="repo",
        branch="main",
        created_at=datetime(2026, 6, 9, 9, tzinfo=UTC),
        updated_at=datetime(2026, 6, 9, 10, tzinfo=UTC),
        selected_model="gpt-5",
        events=(_event(),),
        message_snapshots=(),
        issues=issues,
        source_paths={"events": f"/tmp/{session_id}.jsonl"},
    )


class FakeSyncReader:
    def __init__(self, result: ReadSuccessResult | ReadFailureResult) -> None:
        self._result = result
        self.calls: list[str] = []

    def read(self) -> ReadSuccessResult | ReadFailureResult:
        self.calls.append("read")
        return self._result


class CountingRepository:
    def __init__(self, repository: FakeBigQueryReadModelRepository) -> None:
        self._repository = repository
        self.calls: list[str] = []

    def list_sessions(
        self,
        criteria: SessionListCriteria,
        options: RepositoryExecutionOptions,
    ) -> SessionListResult:
        self.calls.append("list_sessions")
        return self._repository.list_sessions(criteria, options)

    def get_session_detail(
        self,
        session_id: str,
        options: RepositoryExecutionOptions,
    ) -> SessionDetailResult:
        self.calls.append("get_session_detail")
        return self._repository.get_session_detail(session_id, options)

    def save_sessions(
        self,
        rows: Sequence[object],
        options: RepositoryExecutionOptions,
    ) -> SyncWriteResult:
        self.calls.append("save_sessions")
        return self._repository.save_sessions(rows, options)

    def save_sync_run(
        self,
        row: Any,
        options: RepositoryExecutionOptions,
    ) -> SyncRunResult:
        self.calls.append("save_sync_run")
        result = self._repository.save_sync_run(row, options)
        if result is None:
            raise AssertionError("save_sync_run should return a result when options are provided")
        return result

    def start_sync_run(
        self,
        row: Any,
        options: RepositoryExecutionOptions,
    ) -> SyncRunStartResult:
        self.calls.append("start_sync_run")
        return self._repository.start_sync_run(row, options)

    def finish_sync_run(
        self,
        row: Any,
        options: RepositoryExecutionOptions,
    ) -> SyncRunResult:
        self.calls.append("finish_sync_run")
        return self._repository.finish_sync_run(row, options)

    def find_running_sync_run(
        self,
        options: RepositoryExecutionOptions,
    ) -> SyncRunLookupResult:
        self.calls.append("find_running_sync_run")
        return self._repository.find_running_sync_run(options)


class FailingDetailRepository(FakeBigQueryReadModelRepository):
    def get_session_detail(
        self,
        session_id: str,
        options: RepositoryExecutionOptions | None = None,
    ) -> SessionDetailResult:
        _ = session_id, options
        return SessionDetailResult.failure(
            RepositoryError(kind="query_failed", message="fake detail lookup failed")
        )


class FinishFailureRepository(FakeBigQueryReadModelRepository):
    def finish_sync_run(
        self,
        row: Any,
        options: RepositoryExecutionOptions | None = None,
    ) -> SyncRunResult:
        _ = row, options
        return SyncRunResult.failure(
            RepositoryError(
                kind="query_failed",
                message="fake sync run finish failed",
                details={"mode": "finish_failure"},
            )
        )


def _reader_success(*sessions: NormalizedSession) -> ReadSuccessResult:
    return ReadSuccessResult(
        root=ResolvedHistoryRoot(
            requested_root="/tmp/copilot",
            current_root="/tmp/copilot/session-state",
            legacy_root="/tmp/copilot/history-session-state",
        ),
        sessions=sessions,
    )


# 概要・目的: 一覧 service が保存済み read model summary を response data として返す契約を守る。
# テストケース: complete と degraded の fake row を持つ repository に有効 criteria で
# 一覧を要求する。
# 期待値: data は summary payload のみで、meta.count と partial_results が degraded 有無を反映する。
def test_history_api_service_lists_saved_session_summaries() -> None:
    repository = build_history_api_test_repository()
    service = HistoryApiService(repository=repository)

    result = service.list_sessions(_criteria())

    assert result.kind == "success"
    assert result.status == 200
    assert result.data is not None
    assert [session["id"] for session in result.data] == ["complete-session", "degraded-session"]
    assert result.meta == {"count": 2, "partial_results": True}
    assert result.error is None


# 概要・目的: 一致なしの一覧が失敗ではなく空の成功 response になる契約を守る。
# テストケース: 存在しない検索語を指定して一覧 service を呼ぶ。
# 期待値: data は空配列、meta.count は 0、partial_results は false になる。
def test_history_api_service_returns_empty_list_meta_when_no_sessions_match() -> None:
    repository = build_history_api_test_repository()
    service = HistoryApiService(repository=repository)

    result = service.list_sessions(_criteria(search_term="not-found"))

    assert result.kind == "success"
    assert result.status == 200
    assert result.data == []
    assert result.meta == {"count": 0, "partial_results": False}


# 概要・目的: 一覧取得が read-only operation に閉じる契約を守る。
# テストケース: call counter 付き repository で list_sessions service を実行する。
# 期待値: repository の list_sessions だけが呼ばれ、detail / sync / write 系 method は呼ばれない。
def test_history_api_service_list_flow_is_read_only() -> None:
    repository = CountingRepository(build_history_api_test_repository())
    service = HistoryApiService(repository=repository)

    result = service.list_sessions(_criteria())

    assert result.kind == "success"
    assert repository.calls == ["list_sessions"]


# 概要・目的: default 詳細 response では保存済み raw-capable payload から raw 値を抑制する。
# テストケース: raw_payload を持つ snapshot、activity、timeline を include_raw=false で変換する。
# 期待値: raw_included は false、raw_payload は null になり、raw 以外の構造は維持される。
def test_detail_payload_filter_suppresses_raw_payload_fields_by_default() -> None:
    payload = {
        "id": "complete-session",
        "raw_included": True,
        "message_snapshots": [{"role": "assistant", "raw_payload": {"content": "answer"}}],
        "conversation": {"entries": [], "message_count": 0, "empty_reason": None},
        "activity": {
            "entries": [{"title": "tool", "raw_available": True, "raw_payload": {"a": 1}}]
        },
        "timeline": [{"sequence": 1, "raw_payload": {"event": "raw"}}],
        "issues": [],
        "degraded": False,
    }

    filtered = detail_payload_for_response(payload, include_raw=False)
    snapshots = cast(list[dict[str, object]], filtered["message_snapshots"])
    activity = cast(dict[str, object], filtered["activity"])
    activity_entries = cast(list[dict[str, object]], activity["entries"])
    timeline = cast(list[dict[str, object]], filtered["timeline"])

    assert filtered["raw_included"] is False
    assert snapshots[0]["raw_payload"] is None
    assert activity_entries[0]["raw_payload"] is None
    assert activity_entries[0]["raw_available"] is True
    assert timeline[0]["raw_payload"] is None
    assert filtered["conversation"] == {"entries": [], "message_count": 0, "empty_reason": None}


# 概要・目的: raw opt-in 詳細 response が保存済み raw 値を再読取なしで保持する契約を守る。
# テストケース: raw_payload を持つ payload を include_raw=true で変換する。
# 期待値: raw_included は true、raw_payload 実値と raw 以外の field が保持される。
def test_detail_payload_filter_keeps_saved_raw_payloads_when_opted_in() -> None:
    payload = {
        "id": "complete-session",
        "raw_included": True,
        "message_snapshots": [{"role": "assistant", "raw_payload": {"content": "answer"}}],
        "activity": {"entries": [{"title": "tool", "raw_payload": {"a": 1}}]},
        "timeline": [{"sequence": 1, "raw_payload": {"event": "raw"}}],
        "unknown": {"kept": True},
    }

    filtered = detail_payload_for_response(payload, include_raw=True)
    snapshots = cast(list[dict[str, object]], filtered["message_snapshots"])
    activity = cast(dict[str, object], filtered["activity"])
    activity_entries = cast(list[dict[str, object]], activity["entries"])
    timeline = cast(list[dict[str, object]], filtered["timeline"])

    assert filtered["raw_included"] is True
    assert snapshots[0]["raw_payload"] == {"content": "answer"}
    assert activity_entries[0]["raw_payload"] == {"a": 1}
    assert timeline[0]["raw_payload"] == {"event": "raw"}
    assert filtered["unknown"] == {"kept": True}


# 概要・目的: 詳細 service が repository detail payload を raw 指定に応じて返す契約を守る。
# テストケース: 同じ session ID を default と raw opt-in の両方で取得する。
# 期待値: raw_included と raw_payload だけが切り替わり、conversation / activity /
# timeline は保持される。
def test_history_api_service_gets_detail_and_applies_raw_filter() -> None:
    repository = build_history_api_test_repository()
    service = HistoryApiService(repository=repository)

    default_result = service.get_session_detail("complete-session", include_raw=False)
    raw_result = service.get_session_detail("complete-session", include_raw=True)

    assert default_result.kind == "success"
    assert raw_result.kind == "success"
    assert default_result.status == 200
    assert default_result.data["raw_included"] is False
    assert raw_result.data["raw_included"] is True
    assert default_result.data["message_snapshots"][0]["raw_payload"] is None
    assert raw_result.data["message_snapshots"][0]["raw_payload"] == {
        "type": "assistant.message",
        "content": "complete answer",
    }
    assert default_result.data["conversation"] == raw_result.data["conversation"]
    assert default_result.data["activity"] == raw_result.data["activity"]
    assert default_result.data["timeline"] == raw_result.data["timeline"]


# 概要・目的: 存在しない session ID が repository failure と混同されない契約を守る。
# テストケース: missing session の詳細 service result を取得する。
# 期待値: kind は not_found、HTTP status は 404 相当、error code は session_not_found になる。
def test_history_api_service_detail_returns_session_not_found_result() -> None:
    repository = build_history_api_test_repository()
    service = HistoryApiService(repository=repository)

    result = service.get_session_detail("missing-session", include_raw=False)

    assert result.kind == "not_found"
    assert result.status == 404
    assert result.error == {
        "code": "session_not_found",
        "message": "session was not found",
        "details": {"session_id": "missing-session"},
    }


# 概要・目的: repository failure を not found と区別して response 層へ渡す契約を守る。
# テストケース: detail lookup が query_failed を返す repository で詳細 service を呼ぶ。
# 期待値: kind は repository_error になり、RepositoryError が保持される。
def test_history_api_service_detail_keeps_repository_failure_distinct_from_not_found() -> None:
    service = HistoryApiService(repository=FailingDetailRepository())

    result = service.get_session_detail("complete-session", include_raw=False)

    assert result.kind == "repository_error"
    assert result.status == 500
    assert result.repository_error == RepositoryError(
        kind="query_failed",
        message="fake detail lookup failed",
    )


# 概要・目的: 同期 service が request 内で atomic start から保存、finish まで完了する契約を守る。
# テストケース: complete session 2 件を返す fake reader で sync_history を実行する。
# 期待値: start、reader、save_sessions、finish が順に呼ばれ、HTTP 200 相当の
# sync_run と counts が返る。
def test_history_api_service_sync_history_succeeds_with_saved_counts() -> None:
    repository = CountingRepository(FakeBigQueryReadModelRepository())
    reader = FakeSyncReader(_reader_success(_session("session-1"), _session("session-2")))
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "101",
    )

    result = service.sync_history()

    assert result.kind == "success"
    assert result.status == 200
    assert repository.calls == ["start_sync_run", "save_sessions", "finish_sync_run"]
    assert reader.calls == ["read"]
    assert result.data == {
        "sync_run": {
            "id": 101,
            "status": "succeeded",
            "started_at": "2026-06-09T12:00:00Z",
            "finished_at": "2026-06-09T12:00:00Z",
        },
        "counts": {
            "processed_count": 2,
            "inserted_count": 2,
            "updated_count": 0,
            "saved_count": 2,
            "skipped_count": 0,
            "failed_count": 0,
            "degraded_count": 0,
        },
    }


# 概要・目的: degraded session を含む同期完了が error envelope ではなく成功になる契約を守る。
# テストケース: warning issue を持つ degraded session を reader result に含める。
# 期待値: kind は success、sync_run.status は completed_with_issues、degraded_count は 1 になる。
def test_history_api_service_sync_history_completed_with_issues_for_degraded_sessions() -> None:
    issue = ReadIssue(
        code="event.partial",
        message="event was partially mapped",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=1,
    )
    repository = CountingRepository(FakeBigQueryReadModelRepository())
    reader = FakeSyncReader(
        _reader_success(_session("degraded", source_state="degraded", issues=(issue,)))
    )
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "102",
    )

    result = service.sync_history()

    assert result.kind == "success"
    assert result.status == 200
    assert result.data["sync_run"]["status"] == "completed_with_issues"
    assert result.data["counts"]["degraded_count"] == 1
    assert "error" not in cast(dict[str, object], result.data)


# 概要・目的: running sync conflict では reader と session 保存を呼ばない契約を守る。
# テストケース: running sync run を持つ repository で sync_history を実行する。
# 期待値: HTTP 409 相当の history_sync_running error になり、reader / save_sessions は呼ばれない。
def test_history_api_service_sync_history_returns_conflict_without_reading_or_saving() -> None:
    repository = CountingRepository(build_history_api_test_repository(sync_state="running"))
    reader = FakeSyncReader(_reader_success(_session("session-1")))
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "103",
    )

    result = service.sync_history()

    assert result.kind == "sync_conflict"
    assert result.status == 409
    assert repository.calls == ["start_sync_run"]
    assert reader.calls == []
    assert result.error == {
        "code": "history_sync_running",
        "message": "history sync is already running",
        "details": {
            "sync_run_id": "sync-running",
            "started_at": "2026-06-09T10:00:00Z",
        },
    }


# 概要・目的: 履歴 root の読取失敗を空成功ではなく失敗 response へ変換する契約を守る。
# テストケース: reader が root_missing を返す状態で sync_history を実行する。
# 期待値: sync run は failed で finish され、HTTP 503 相当の root failure error が返る。
def test_history_api_service_sync_history_returns_root_failure() -> None:
    repository = CountingRepository(FakeBigQueryReadModelRepository())
    reader = FakeSyncReader(
        ReadFailureResult(
            code="root_missing",
            message="history root does not exist",
            root_path="/tmp/copilot-missing-home/.copilot",
        )
    )
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "104",
    )

    result = service.sync_history()

    assert result.kind == "sync_error"
    assert result.status == 503
    assert repository.calls == ["start_sync_run", "finish_sync_run"]
    assert result.error == {
        "code": "root_missing",
        "message": "history root does not exist",
        "details": {"path": "/tmp/copilot-missing-home/.copilot"},
    }
    meta = cast(dict[str, dict[str, object]], result.meta)
    assert meta["sync_run"]["status"] == "failed"
    assert meta["counts"]["failed_count"] == 1


# 概要・目的: session 保存失敗を history_sync_failed と sync run meta 付きで返す契約を守る。
# テストケース: save_sessions が query_failed を返す fake repository で sync_history を実行する。
# 期待値: HTTP 500 相当の history_sync_failed error になり、sync run は failed で finish される。
def test_history_api_service_sync_history_returns_persistence_failure() -> None:
    repository = CountingRepository(build_history_api_test_repository(sync_state="save_failure"))
    reader = FakeSyncReader(_reader_success(_session("session-1")))
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "105",
    )

    result = service.sync_history()

    assert result.kind == "sync_error"
    assert result.status == 500
    assert repository.calls == ["start_sync_run", "save_sessions", "finish_sync_run"]
    assert result.error == {
        "code": "history_sync_failed",
        "message": "history sync failed",
        "details": {
            "mode": "save_failure",
            "sync_run_id": 105,
        },
    }
    meta = cast(dict[str, dict[str, object]], result.meta)
    assert meta["sync_run"]["status"] == "failed"


# 概要・目的: sync run finish の保存失敗を成功扱いにしない契約を守る。
# テストケース: session 保存は成功するが finish_sync_run が query_failed を返す repository で
# sync_history を実行する。
# 期待値: HTTP 500 相当の history_sync_failed error になり、成功 data は返らない。
def test_history_api_service_sync_history_returns_failure_when_finish_fails() -> None:
    repository = CountingRepository(FinishFailureRepository())
    reader = FakeSyncReader(_reader_success(_session("session-1")))
    service = HistoryApiService(
        repository=repository,
        reader=reader,
        clock=lambda: datetime(2026, 6, 9, 12, tzinfo=UTC),
        sync_run_id_factory=lambda: "106",
    )

    result = service.sync_history()

    assert result.kind == "sync_error"
    assert result.status == 500
    assert repository.calls == ["start_sync_run", "save_sessions", "finish_sync_run"]
    assert result.error == {
        "code": "history_sync_failed",
        "message": "history sync failed",
        "details": {
            "mode": "finish_failure",
            "sync_run_id": 106,
        },
    }
    meta = cast(dict[str, dict[str, object]], result.meta)
    assert meta["sync_run"]["status"] == "failed"
    assert result.data is None

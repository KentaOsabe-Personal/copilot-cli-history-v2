from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal

from copilot_history.types import (
    NormalizedEvent,
    NormalizedSession,
    ReadFailureResult,
    ReadIssue,
    ReadSuccessResult,
    ResolvedHistoryRoot,
)
from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
)
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

HistoryApiFakeSyncState = Literal["idle", "running", "save_failure"]

NOW = datetime(2026, 6, 9, 10, tzinfo=UTC)


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
        rows: Sequence[Any],
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


class SaveFailureFakeRepository(FakeBigQueryReadModelRepository):
    def save_sessions(
        self,
        rows: Sequence[object],
        options: RepositoryExecutionOptions | None = None,
    ) -> SyncWriteResult:
        return SyncWriteResult.failure(
            RepositoryError(
                kind="query_failed",
                message="fake repository save failed",
                details={"mode": "save_failure"},
            )
        )


def build_history_api_test_repository(
    *,
    sync_state: HistoryApiFakeSyncState = "idle",
) -> FakeBigQueryReadModelRepository:
    repository: FakeBigQueryReadModelRepository
    if sync_state == "save_failure":
        repository = SaveFailureFakeRepository()
    else:
        repository = FakeBigQueryReadModelRepository()

    repository.save_session(_complete_session_row())
    repository.save_session(_degraded_session_row())
    if sync_state == "running":
        repository.save_sync_run(_running_sync_run_row())
    return repository


def sync_reader_success(
    *sessions: NormalizedSession,
) -> ReadSuccessResult:
    return ReadSuccessResult(
        root=ResolvedHistoryRoot(
            requested_root="/tmp/copilot",
            current_root="/tmp/copilot/session-state",
            legacy_root="/tmp/copilot/history-session-state",
        ),
        sessions=sessions,
    )


def sync_reader_root_failure() -> ReadFailureResult:
    return ReadFailureResult(
        code="root_missing",
        message="history root does not exist",
        root_path="/tmp/copilot-missing-home/.copilot",
    )


def normalized_session(
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


def degraded_issue() -> ReadIssue:
    return ReadIssue(
        code="event.partial",
        message="event was partially mapped",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=1,
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


def _complete_session_row() -> CopilotSessionRow:
    return _session_row(
        session_id="complete-session",
        source_state="complete",
        degraded=False,
        summary_payload={
            "id": "complete-session",
            "source_format": "current",
            "created_at": "2026-06-09T10:00:00Z",
            "updated_at": "2026-06-09T10:00:00Z",
            "work_context": {
                "cwd": "/workspace",
                "git_root": "/workspace",
                "repository": "repo",
                "branch": "main",
            },
            "selected_model": "gpt-5",
            "source_state": "complete",
            "event_count": 1,
            "message_snapshot_count": 1,
            "conversation_summary": {
                "has_conversation": True,
                "message_count": 1,
                "preview": "complete answer",
                "activity_count": 0,
            },
            "degraded": False,
            "issues": [],
        },
        detail_payload={
            "id": "complete-session",
            "source_format": "current",
            "created_at": "2026-06-09T10:00:00Z",
            "updated_at": "2026-06-09T10:00:00Z",
            "raw_included": True,
            "message_snapshots": [
                {
                    "role": "assistant",
                    "content": "complete answer",
                    "raw_payload": {
                        "type": "assistant.message",
                        "content": "complete answer",
                    },
                }
            ],
            "conversation": {
                "entries": [],
                "message_count": 0,
                "empty_reason": None,
                "summary": {
                    "has_conversation": True,
                    "message_count": 1,
                    "preview": "complete answer",
                    "activity_count": 0,
                },
            },
            "activity": {"entries": []},
            "timeline": [],
            "issues": [],
            "degraded": False,
        },
    )


def _degraded_session_row() -> CopilotSessionRow:
    return _session_row(
        session_id="degraded-session",
        source_state="degraded",
        degraded=True,
        summary_payload={
            "id": "degraded-session",
            "source_format": "current",
            "created_at": "2026-06-09T09:00:00Z",
            "updated_at": "2026-06-09T09:00:00Z",
            "work_context": {
                "cwd": "/workspace",
                "git_root": "/workspace",
                "repository": "repo",
                "branch": "main",
            },
            "selected_model": "gpt-5",
            "source_state": "degraded",
            "event_count": 1,
            "message_snapshot_count": 0,
            "conversation_summary": {
                "has_conversation": False,
                "message_count": 0,
                "preview": None,
                "activity_count": 1,
            },
            "degraded": True,
            "issues": [
                {
                    "code": "event.partial",
                    "severity": "warning",
                    "message": "event was partially mapped",
                    "source_path": "/tmp/events.jsonl",
                    "scope": "event",
                    "event_sequence": 1,
                }
            ],
        },
        detail_payload={
            "id": "degraded-session",
            "raw_included": True,
            "message_snapshots": [],
            "conversation": {
                "entries": [],
                "message_count": 0,
                "empty_reason": "no_conversation_messages",
                "summary": {
                    "has_conversation": False,
                    "message_count": 0,
                    "preview": None,
                    "activity_count": 1,
                },
            },
            "activity": {"entries": []},
            "timeline": [],
            "issues": [],
            "degraded": True,
        },
    )


def _session_row(
    *,
    session_id: str,
    source_state: str,
    degraded: bool,
    summary_payload: dict[str, object],
    detail_payload: dict[str, object],
) -> CopilotSessionRow:
    return CopilotSessionRow(
        session_id=session_id,
        source_format="current",
        source_state=source_state,
        created_at_source=NOW,
        updated_at_source=NOW,
        source_partition_date=date(2026, 6, 9),
        cwd="/workspace",
        git_root="/workspace",
        repository="repo",
        branch="main",
        selected_model="gpt-5",
        event_count=1,
        message_snapshot_count=1,
        issue_count=1 if degraded else 0,
        message_count=1 if not degraded else 0,
        activity_count=0 if not degraded else 1,
        degraded=degraded,
        conversation_preview="complete answer" if not degraded else None,
        source_paths={"events": f"/tmp/{session_id}.jsonl"},
        source_fingerprint={"sha256": session_id},
        summary_payload=summary_payload,
        detail_payload=detail_payload,
        search_text="complete answer" if not degraded else "event was partially mapped",
        search_text_version=2,
        indexed_at=NOW,
    )


def _running_sync_run_row() -> HistorySyncRunRow:
    return HistorySyncRunRow(
        sync_run_id="sync-running",
        status="running",
        started_at=NOW,
        finished_at=None,
        started_partition_date=NOW.date(),
        processed_count=0,
        inserted_count=0,
        updated_count=0,
        saved_count=0,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key="history-sync",
        indexed_at=NOW,
    )

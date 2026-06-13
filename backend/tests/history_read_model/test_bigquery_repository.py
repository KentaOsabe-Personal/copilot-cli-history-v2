from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime

from history_read_model.bigquery_repository import BigQuerySessionReadModelRepository
from history_read_model.bigquery_settings import BigQueryReadModelSettings
from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
)
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


class _QueryJob:
    def __init__(
        self,
        rows: tuple[Mapping[str, object], ...] = (),
        result_error: Exception | None = None,
    ) -> None:
        self._rows = rows
        self._result_error = result_error

    def result(self) -> tuple[Mapping[str, object], ...]:
        if self._result_error is not None:
            raise self._result_error
        return self._rows


class _LoadJob:
    def __init__(self, result_error: Exception | None = None) -> None:
        self._result_error = result_error

    def result(self) -> None:
        if self._result_error is not None:
            raise self._result_error


class _ClientDouble:
    def __init__(
        self,
        query_rows: tuple[tuple[Mapping[str, object], ...], ...] = (),
        query_error: Exception | None = None,
        result_error: Exception | None = None,
        insert_errors: list[object] | None = None,
    ) -> None:
        self.query_rows = list(query_rows)
        self.query_error = query_error
        self.result_error = result_error
        self.insert_errors = insert_errors or []
        self.queries: list[tuple[str, object | None, str | None]] = []
        self.inserted_rows: list[tuple[str, list[dict[str, object]]]] = []
        self.loaded_files: list[tuple[str, list[dict[str, object]], str | None]] = []

    def query(
        self,
        sql: str,
        *,
        job_config: object | None = None,
        location: str | None = None,
    ) -> _QueryJob:
        if self.query_error is not None:
            raise self.query_error
        self.queries.append((sql, job_config, location))
        rows = self.query_rows.pop(0) if self.query_rows else ()
        return _QueryJob(rows, result_error=self.result_error)

    def insert_rows_json(
        self,
        table: str,
        json_rows: list[dict[str, object]],
    ) -> list[object]:
        self.inserted_rows.append((table, json_rows))
        return self.insert_errors

    def load_table_from_file(
        self,
        file_obj: object,
        table: str,
        *,
        job_config: object | None = None,
        location: str | None = None,
    ) -> _LoadJob:
        del job_config
        data = file_obj.read().decode("utf-8")  # type: ignore[attr-defined]
        rows = [json.loads(line) for line in data.splitlines() if line]
        self.loaded_files.append((table, rows, location))
        return _LoadJob(result_error=self.result_error)


def _settings() -> BigQueryReadModelSettings:
    return BigQueryReadModelSettings(
        project_id="local-project",
        dataset_id="history_dataset",
        location="asia-northeast1",
        table_prefix="dev_",
        credentials_path=None,
        maximum_bytes_billed_default=2048,
    )


def _row(session_id: str, *, fingerprint: Mapping[str, object] | None = None) -> CopilotSessionRow:
    now = datetime(2026, 6, 9, 10, tzinfo=UTC)
    return CopilotSessionRow(
        session_id=session_id,
        source_format="current",
        source_state="complete",
        created_at_source=now,
        updated_at_source=now,
        source_partition_date=date(2026, 6, 9),
        cwd="/workspace",
        git_root="/workspace",
        repository="repo",
        branch="main",
        selected_model="gpt-5",
        event_count=1,
        message_snapshot_count=1,
        issue_count=0,
        message_count=1,
        activity_count=0,
        degraded=False,
        conversation_preview="preview",
        source_paths={"primary": f"/workspace/{session_id}.json"},
        source_fingerprint=fingerprint or {"sha256": session_id},
        summary_payload={"id": session_id},
        detail_payload={"id": session_id, "messages": []},
        search_text="preview",
        search_text_version=2,
        indexed_at=now,
    )


def _sync_run_row(sync_run_id: str) -> HistorySyncRunRow:
    started_at = datetime(2026, 6, 9, 10, tzinfo=UTC)
    return HistorySyncRunRow(
        sync_run_id=sync_run_id,
        status="running",
        started_at=started_at,
        finished_at=None,
        started_partition_date=started_at.date(),
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
        indexed_at=started_at,
    )


def _finished_sync_run_row(sync_run_id: str) -> HistorySyncRunRow:
    started_at = datetime(2026, 6, 9, 10, tzinfo=UTC)
    finished_at = datetime(2026, 6, 9, 10, 1, tzinfo=UTC)
    return HistorySyncRunRow(
        sync_run_id=sync_run_id,
        status="succeeded",
        started_at=started_at,
        finished_at=finished_at,
        started_partition_date=started_at.date(),
        processed_count=2,
        inserted_count=1,
        updated_count=1,
        saved_count=2,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key=None,
        indexed_at=finished_at,
    )


def _job_config_values(job_config: object) -> dict[str, object]:
    return {
        key: getattr(job_config, key)
        for key in ("dry_run", "maximum_bytes_billed", "query_parameters")
        if hasattr(job_config, key)
    }


# 概要・目的: BigQuery adapter が list criteria validation を BigQuery job 作成前に行う。
# テストケース: date range 欠落 criteria で list_sessions を呼ぶ。
# 期待値: missing_date_range error が返り、client.query は呼ばれない。
def test_bigquery_repository_list_sessions_rejects_missing_range_before_query() -> None:
    client = _ClientDouble()
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.list_sessions(
        SessionListCriteria(from_datetime=None, to_datetime=datetime(2026, 6, 9, tzinfo=UTC)),
        RepositoryExecutionOptions(),
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.kind == "missing_date_range"
    assert client.queries == []


# 概要・目的: BigQuery adapter が read query に job config と location を適用して payload を返す。
# テストケース: list と detail を client double の rows 付きで呼ぶ。
# 期待値: summary/detail payload が透過的に返り、maximum bytes billed と location が渡る。
def test_bigquery_repository_reads_payloads_with_job_options() -> None:
    client = _ClientDouble(
        query_rows=(
            ({"summary_payload": {"id": "session-1"}},),
            ({"detail_payload": {"id": "session-1", "messages": []}},),
        )
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())
    options = RepositoryExecutionOptions(maximum_bytes_billed=1024, location="US")

    list_result = repository.list_sessions(
        SessionListCriteria(
            from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
            to_datetime=datetime(2026, 6, 9, tzinfo=UTC),
        ),
        options,
    )
    detail_result = repository.get_session_detail("session-1", options)

    assert list_result.ok is True
    assert list_result.summary_payloads == ({"id": "session-1"},)
    assert detail_result.ok is True
    assert detail_result.detail_payload == {"id": "session-1", "messages": []}
    assert client.queries[0][2] == "US"
    assert _job_config_values(client.queries[0][1])["maximum_bytes_billed"] == 1024


# 概要・目的: BigQuery adapter の save_sessions dry run が metadata lookup と分類だけを実行する。
# テストケース: metadata に一致する既存 row を返し、dry_run で save_sessions を呼ぶ。
# 期待値: MERGE/staging mutation は行われず、skip count と dry-run plan が返る。
def test_bigquery_repository_save_sessions_dry_run_skips_mutation_after_planning() -> None:
    client = _ClientDouble(
        query_rows=(
            (
                {
                    "session_id": "same",
                    "source_fingerprint": {"sha256": "same"},
                    "search_text_version": 2,
                },
            ),
        )
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.save_sessions(
        (_row("same", fingerprint={"sha256": "same"}),),
        RepositoryExecutionOptions(dry_run=True),
    )

    assert result.ok is True
    assert result.dry_run is True
    assert result.skipped_count == 1
    assert result.saved_count == 0
    assert len(client.queries) == 1
    assert client.inserted_rows == []


# 概要・目的: BigQuery adapter が insert/update 対象だけを staging と MERGE に送ることを守る。
# テストケース: 新規 row、更新 row、skip row を save_sessions に渡す。
# 期待値: insert/update の 2 row だけが staging に投入され、MERGE query が実行される。
def test_bigquery_repository_save_sessions_stages_and_merges_only_changed_rows() -> None:
    client = _ClientDouble(
        query_rows=(
            (
                {
                    "session_id": "updated",
                    "source_fingerprint": {"sha256": "old"},
                    "search_text_version": 2,
                },
                {
                    "session_id": "skipped",
                    "source_fingerprint": {"sha256": "same"},
                    "search_text_version": 2,
                },
            ),
            (),
        )
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())
    inserted = _row("inserted")
    updated = _row("updated", fingerprint={"sha256": "new"})
    skipped = _row("skipped", fingerprint={"sha256": "same"})

    result = repository.save_sessions((inserted, updated, skipped), RepositoryExecutionOptions())

    assert result.ok is True
    assert result.inserted_count == 1
    assert result.updated_count == 1
    assert result.skipped_count == 1
    assert len(client.queries) == 2
    assert len(client.loaded_files) == 1
    assert [row["session_id"] for row in client.loaded_files[0][1]] == ["inserted", "updated"]
    assert client.loaded_files[0][1][0]["created_at_source"] == "2026-06-09T10:00:00+00:00"
    assert client.loaded_files[0][1][0]["source_partition_date"] == "2026-06-09"
    assert client.loaded_files[0][1][0]["summary_payload"] == '{"id":"inserted"}'
    assert any(
        "MERGE `local-project.history_dataset.dev_copilot_sessions`" in sql
        for sql, _, _ in client.queries
    )


# 概要・目的: BigQuery adapter が大きな同期を streaming insert ではなく load job に送る契約を守る。
# テストケース: 51 件の新規 row を save_sessions に渡す。
# 期待値: staging load job に全 row が渡され、保存 count は維持される。
def test_bigquery_repository_save_sessions_loads_staging_rows_with_load_job() -> None:
    client = _ClientDouble(query_rows=((), (),))
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())
    rows = tuple(_row(f"inserted-{index:02d}") for index in range(51))

    result = repository.save_sessions(rows, RepositoryExecutionOptions())

    assert result.ok is True
    assert result.inserted_count == 51
    assert client.inserted_rows == []
    assert len(client.loaded_files) == 1
    assert len(client.loaded_files[0][1]) == 51
    assert client.loaded_files[0][2] == "asia-northeast1"


# 概要・目的: BigQuery adapter が sync run 保存と running lookup を query operation として実行する。
# テストケース: sync run upsert と running lookup を client double で呼ぶ。
# 期待値: history_sync_runs の MERGE と running lookup が実行され、repository result が返る。
def test_bigquery_repository_saves_sync_run_and_finds_running_sync_run() -> None:
    client = _ClientDouble(
        query_rows=(
            (),
            (
                {
                    "sync_run_id": "sync-running",
                    "started_at": datetime(2026, 6, 9, 10, tzinfo=UTC),
                },
            ),
        )
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    saved = repository.save_sync_run(_sync_run_row("sync-running"), RepositoryExecutionOptions())
    running = repository.find_running_sync_run(RepositoryExecutionOptions())

    assert saved.ok is True
    assert saved.sync_run_id == "sync-running"
    assert running.ok is True
    assert running.found is True
    assert running.sync_run_id == "sync-running"
    assert running.started_at == datetime(2026, 6, 9, 10, tzinfo=UTC)
    assert "history_sync_runs" in client.queries[0][0]
    assert "running_lock_key IS NOT NULL" in client.queries[1][0]


# 概要・目的: fake repository が同期開始を running lock として扱い、重複開始を conflict にする。
# テストケース: running row で start_sync_run を 2 回呼び、2 回目は別 ID を指定する。
# 期待値: 1 回目は started、2 回目は既存 sync_run_id と started_at を持つ conflict になる。
def test_fake_repository_start_sync_run_returns_conflict_with_started_at() -> None:
    repository = FakeBigQueryReadModelRepository()
    running = _sync_run_row("sync-running")

    started = repository.start_sync_run(running, RepositoryExecutionOptions())
    conflict = repository.start_sync_run(_sync_run_row("sync-next"), RepositoryExecutionOptions())

    assert started.ok is True
    assert started.started is True
    assert started.sync_run_id == "sync-running"
    assert conflict.ok is True
    assert conflict.started is False
    assert conflict.conflict is not None
    assert conflict.conflict.sync_run_id == "sync-running"
    assert conflict.conflict.started_at == running.started_at


# 概要・目的: fake repository が同じ lifecycle 上で同期終了を保存できることを守る。
# テストケース: running start 後に terminal row で finish_sync_run を呼ぶ。
# 期待値: sync run は terminal status に更新され、running lookup から消える。
def test_fake_repository_finish_sync_run_releases_running_lock() -> None:
    repository = FakeBigQueryReadModelRepository()
    repository.start_sync_run(_sync_run_row("sync-running"), RepositoryExecutionOptions())

    finished = repository.finish_sync_run(
        _finished_sync_run_row("sync-running"),
        RepositoryExecutionOptions(),
    )
    running = repository.find_running_sync_run(RepositoryExecutionOptions())
    saved_row = repository.get_sync_run("sync-running")

    assert finished.ok is True
    assert finished.sync_run_id == "sync-running"
    assert saved_row is not None
    assert saved_row.status == "succeeded"
    assert running.ok is True
    assert running.found is False


# 概要・目的: BigQuery adapter が start_sync_run を単一 query operation として実行する。
# テストケース: client double が started=true の row を返す状態で start_sync_run を呼ぶ。
# 期待値: result は started になり、query には running conflict 判定と upsert が含まれる。
def test_bigquery_repository_start_sync_run_uses_atomic_query_result() -> None:
    started_at = datetime(2026, 6, 9, 10, tzinfo=UTC)
    client = _ClientDouble(
        query_rows=(({"started": True, "sync_run_id": "sync-running", "started_at": started_at},),)
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.start_sync_run(_sync_run_row("sync-running"), RepositoryExecutionOptions())

    assert result.ok is True
    assert result.started is True
    assert result.sync_run_id == "sync-running"
    assert len(client.queries) == 1
    assert "IF running_sync_run_id IS NULL THEN" in client.queries[0][0]
    assert "MERGE `local-project.history_dataset.dev_history_sync_runs`" in client.queries[0][0]


# 概要・目的: BigQuery adapter が running conflict を既存 sync_run_id と started_at で返す。
# テストケース: atomic start query の結果 row に started=false と既存実行情報を返す。
# 期待値: reader や保存処理に進む前に conflict として識別できる result になる。
def test_bigquery_repository_start_sync_run_maps_conflict_result() -> None:
    started_at = datetime(2026, 6, 9, 9, 59, tzinfo=UTC)
    client = _ClientDouble(
        query_rows=(
            (
                {
                    "started": False,
                    "sync_run_id": "sync-existing",
                    "started_at": started_at,
                },
            ),
        )
    )
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.start_sync_run(_sync_run_row("sync-next"), RepositoryExecutionOptions())

    assert result.ok is True
    assert result.started is False
    assert result.conflict is not None
    assert result.conflict.sync_run_id == "sync-existing"
    assert result.conflict.started_at == started_at


# 概要・目的: BigQuery adapter が client query 例外を repository error として分類する。
# テストケース: permission denied 相当の例外を client.query から送出する。
# 期待値: list_sessions は success ではなく permission_denied error を返す。
def test_bigquery_repository_maps_client_query_exception_to_repository_error() -> None:
    class Forbidden(Exception):
        pass

    client = _ClientDouble(query_error=Forbidden("access denied"))
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.list_sessions(
        SessionListCriteria(
            from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
            to_datetime=datetime(2026, 6, 9, tzinfo=UTC),
        ),
        RepositoryExecutionOptions(),
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.kind == "permission_denied"


# 概要・目的: BigQuery adapter が job result failure を success として扱わない契約を守る。
# テストケース: maximum bytes billed 超過相当の例外を job.result から送出する。
# 期待値: detail lookup は cost_limit_exceeded error を返す。
def test_bigquery_repository_maps_job_result_failure_to_repository_error() -> None:
    class BillingLimitExceeded(Exception):
        def __init__(self) -> None:
            self.errors = [{"reason": "billingTierLimitExceeded"}]
            super().__init__("maximum bytes billed exceeded")

    client = _ClientDouble(result_error=BillingLimitExceeded())
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.get_session_detail("session-1", RepositoryExecutionOptions())

    assert result.ok is False
    assert result.error is not None
    assert result.error.kind == "cost_limit_exceeded"


# 概要・目的: BigQuery adapter が staging load failure を row-level failed count と混同しない。
# テストケース: load job の result が BigQuery load error を送出する。
# 期待値: save_sessions は repository-level query_failed error になり、success count を返さない。
def test_bigquery_repository_maps_staging_load_failure_to_repository_error() -> None:
    client = _ClientDouble(query_rows=((),), result_error=RuntimeError("invalid row"))
    repository = BigQuerySessionReadModelRepository(client=client, settings=_settings())

    result = repository.save_sessions((_row("inserted"),), RepositoryExecutionOptions())

    assert result.ok is False
    assert result.error is not None
    assert result.error.kind == "query_failed"
    assert result.failed_count == 0

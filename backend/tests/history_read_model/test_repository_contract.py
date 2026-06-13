from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pytest

from history_read_model.bigquery_repository import BigQuerySessionReadModelRepository
from history_read_model.bigquery_settings import BigQueryReadModelSettings
from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
)
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


class _QueryJob:
    def __init__(self, rows: tuple[Mapping[str, object], ...] = ()) -> None:
        self._rows = rows

    def result(self) -> tuple[Mapping[str, object], ...]:
        return self._rows


class _ClientDouble:
    def __init__(self, query_rows: tuple[tuple[Mapping[str, object], ...], ...] = ()) -> None:
        self.query_rows = list(query_rows)
        self.queries: list[str] = []
        self.inserted_rows: list[tuple[str, list[dict[str, object]]]] = []

    def query(
        self,
        sql: str,
        *,
        job_config: object | None = None,
        location: str | None = None,
    ) -> _QueryJob:
        self.queries.append(sql)
        rows = self.query_rows.pop(0) if self.query_rows else ()
        return _QueryJob(rows)

    def insert_rows_json(
        self,
        table: str,
        json_rows: list[dict[str, object]],
    ) -> list[object]:
        self.inserted_rows.append((table, json_rows))
        return []


@dataclass(frozen=True)
class _RepositoryCase:
    name: str
    repository: Any
    client: _ClientDouble | None = None


def _settings() -> BigQueryReadModelSettings:
    return BigQueryReadModelSettings(
        project_id="local-project",
        dataset_id="history_dataset",
        location="asia-northeast1",
        table_prefix="dev_",
        credentials_path=None,
        maximum_bytes_billed_default=2048,
    )


def _row(
    session_id: str,
    *,
    created_at_source: datetime | None = None,
    updated_at_source: datetime | None = None,
    degraded: bool = False,
    fingerprint: Mapping[str, object] | None = None,
) -> CopilotSessionRow:
    display_time = updated_at_source or created_at_source or datetime(2026, 6, 9, tzinfo=UTC)
    return CopilotSessionRow(
        session_id=session_id,
        source_format="current",
        source_state="complete",
        created_at_source=created_at_source or display_time,
        updated_at_source=updated_at_source,
        source_partition_date=date(2026, 6, 9),
        cwd=f"/workspace/{session_id}",
        git_root="/workspace",
        repository="repo",
        branch="main",
        selected_model="gpt-5",
        event_count=1,
        message_snapshot_count=1,
        issue_count=1 if degraded else 0,
        message_count=1,
        activity_count=0,
        degraded=degraded,
        conversation_preview="preview",
        source_paths={"primary": f"/workspace/{session_id}.json"},
        source_fingerprint=fingerprint or {"sha256": session_id},
        summary_payload={"id": session_id, "title": f"Summary {session_id}"},
        detail_payload={"id": session_id, "degraded": degraded, "issues": []},
        search_text=f"preview {session_id}",
        search_text_version=2,
        indexed_at=datetime(2026, 6, 9, 12, tzinfo=UTC),
    )


def _criteria() -> SessionListCriteria:
    return SessionListCriteria(
        from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
        to_datetime=datetime(2026, 6, 30, tzinfo=UTC),
        search_term="preview",
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


def _fake_with_rows() -> _RepositoryCase:
    repository = FakeBigQueryReadModelRepository()
    repository.save_session(
        _row("later", updated_at_source=datetime(2026, 6, 9, 10, tzinfo=UTC))
    )
    repository.save_session(
        _row("earlier", updated_at_source=datetime(2026, 6, 8, 10, tzinfo=UTC))
    )
    return _RepositoryCase(name="fake", repository=repository)


def _bigquery_with_rows() -> _RepositoryCase:
    client = _ClientDouble(
        query_rows=(
            (
                {"summary_payload": {"id": "later", "title": "Summary later"}},
                {"summary_payload": {"id": "earlier", "title": "Summary earlier"}},
            ),
        )
    )
    return _RepositoryCase(
        name="bigquery",
        repository=BigQuerySessionReadModelRepository(client=client, settings=_settings()),
        client=client,
    )


@pytest.mark.parametrize("case_factory", (_fake_with_rows, _bigquery_with_rows))
# 概要・目的: fake と BigQuery adapter が同じ一覧 contract assertion で検証される状態を守る。
# テストケース: 保存済み summary payload を date range / search 条件で list する。
# 期待値: 両 adapter とも同じ代表順序の summary payload を success として返す。
def test_repository_contract_lists_sessions_with_shared_assertions(
    case_factory: Callable[[], _RepositoryCase],
) -> None:
    case = case_factory()

    result = case.repository.list_sessions(_criteria(), RepositoryExecutionOptions())

    assert result.ok is True
    assert tuple(payload["id"] for payload in result.summary_payloads) == ("later", "earlier")


@pytest.mark.parametrize(
    "case_factory",
    (
        lambda: _RepositoryCase(
            name="fake",
            repository=FakeBigQueryReadModelRepository(),
        ),
        lambda: _RepositoryCase(
            name="bigquery",
            repository=BigQuerySessionReadModelRepository(
                client=_ClientDouble(query_rows=((),)),
                settings=_settings(),
            ),
        ),
    ),
)
# 概要・目的: fake と BigQuery adapter が detail not found を error と混同しない契約を守る。
# テストケース: 存在しない session_id で detail lookup する。
# 期待値: 両 adapter とも success not_found を返す。
def test_repository_contract_distinguishes_detail_not_found(
    case_factory: Callable[[], _RepositoryCase],
) -> None:
    case = case_factory()

    result = case.repository.get_session_detail("missing", RepositoryExecutionOptions())

    assert result.ok is True
    assert result.found is False
    assert result.session_id == "missing"


@pytest.mark.parametrize(
    "case_factory",
    (
        lambda: _RepositoryCase(
            name="fake",
            repository=FakeBigQueryReadModelRepository(),
        ),
        lambda: _RepositoryCase(
            name="bigquery",
            repository=BigQuerySessionReadModelRepository(
                client=_ClientDouble(query_rows=((), ())),
                settings=_settings(),
            ),
        ),
    ),
)
# 概要・目的: fake と BigQuery adapter の保存 count が同じ write plan に基づくことを守る。
# テストケース: 新規 row と degraded row を save_sessions に渡す。
# 期待値: 両 adapter とも inserted/saved/degraded の count が一致する。
def test_repository_contract_save_sessions_counts_inserted_and_degraded_rows(
    case_factory: Callable[[], _RepositoryCase],
) -> None:
    case = case_factory()
    rows = (
        _row("inserted", updated_at_source=datetime(2026, 6, 9, 10, tzinfo=UTC)),
        _row(
            "degraded",
            updated_at_source=datetime(2026, 6, 9, 11, tzinfo=UTC),
            degraded=True,
        ),
    )

    result = case.repository.save_sessions(rows, RepositoryExecutionOptions())

    assert result.ok is True
    assert result.processed_count == 2
    assert result.inserted_count == 2
    assert result.updated_count == 0
    assert result.saved_count == 2
    assert result.degraded_count == 1


@pytest.mark.parametrize(
    "case_factory",
    (
        lambda: _RepositoryCase(
            name="fake",
            repository=FakeBigQueryReadModelRepository(),
        ),
        lambda: _RepositoryCase(
            name="bigquery",
            repository=BigQuerySessionReadModelRepository(
                client=_ClientDouble(query_rows=((), ({"sync_run_id": "sync-1"},))),
                settings=_settings(),
            ),
        ),
    ),
)
# 概要・目的: fake と BigQuery adapter が sync run の running 状態を同じ contract で扱う。
# テストケース: running sync run を保存し、running lookup を実行する。
# 期待値: 両 adapter とも running sync_run_id を found として返す。
def test_repository_contract_saves_and_finds_running_sync_run(
    case_factory: Callable[[], _RepositoryCase],
) -> None:
    case = case_factory()

    saved = case.repository.save_sync_run(_sync_run_row("sync-1"), RepositoryExecutionOptions())
    lookup = case.repository.find_running_sync_run(RepositoryExecutionOptions())

    assert saved.ok is True
    assert saved.sync_run_id == "sync-1"
    assert lookup.ok is True
    assert lookup.found is True
    assert lookup.sync_run_id == "sync-1"

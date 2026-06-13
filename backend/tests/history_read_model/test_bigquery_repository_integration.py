from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from history_read_model.bigquery_repository import BigQuerySessionReadModelRepository
from history_read_model.bigquery_settings import (
    BigQuerySettingsError,
    load_bigquery_settings,
    read_bigquery_integration_enabled,
)
from history_read_model.fake_repository import CopilotSessionRow
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


def _integration_repository() -> BigQuerySessionReadModelRepository:
    if not read_bigquery_integration_enabled():
        pytest.skip("BIGQUERY_READ_MODEL_INTEGRATION is not enabled")
    try:
        settings = load_bigquery_settings(require_credentials=True)
    except BigQuerySettingsError as exc:
        pytest.skip(f"BigQuery integration settings are incomplete: {exc}")
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        pytest.skip(f"google-cloud-bigquery is unavailable: {exc}")
    return BigQuerySessionReadModelRepository(
        client=bigquery.Client(project=settings.project_id),
        settings=settings,
    )


def _integration_row() -> CopilotSessionRow:
    now = datetime(2026, 6, 9, 12, tzinfo=UTC)
    return CopilotSessionRow(
        session_id="integration-contract-dry-run",
        source_format="current",
        source_state="complete",
        created_at_source=now,
        updated_at_source=now,
        source_partition_date=date(2026, 6, 9),
        cwd="/workspace/integration",
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
        conversation_preview="integration",
        source_paths={"primary": "/workspace/integration.json"},
        source_fingerprint={"sha256": "integration-contract-dry-run"},
        summary_payload={"id": "integration-contract-dry-run"},
        detail_payload={"id": "integration-contract-dry-run", "messages": []},
        search_text="integration",
        search_text_version=2,
        indexed_at=now,
    )


def _skip_if_integration_precondition_missing(error_kind: str | None) -> None:
    if error_kind in {
        "credentials_error",
        "permission_denied",
        "schema_mismatch",
    }:
        pytest.skip(f"BigQuery integration precondition is unavailable: {error_kind}")


# 概要・目的: opt-in 条件がない通常環境では BigQuery 実接続 test を skip する契約を守る。
# テストケース: integration repository fixture を作成する。
# 期待値: flag/env/credentials が揃う場合だけ BigQuery client backed repository が返る。
def test_bigquery_repository_integration_is_explicitly_gated() -> None:
    repository = _integration_repository()

    assert isinstance(repository, BigQuerySessionReadModelRepository)


# 概要・目的: opt-in BigQuery integration で代表 read と write dry run が実接続経路を通る。
# テストケース: date range list、missing detail、save_sessions dry run を実 dataset 前提で実行する。
# 期待値: credentials/env が揃う場合だけ実行され、query 失敗は repository error として露出する。
def test_bigquery_repository_integration_read_and_write_paths() -> None:
    repository = _integration_repository()
    options = RepositoryExecutionOptions(dry_run=True)

    list_result = repository.list_sessions(
        SessionListCriteria(
            from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
            to_datetime=datetime(2026, 6, 30, tzinfo=UTC),
            limit=1,
        ),
        RepositoryExecutionOptions(),
    )
    detail_result = repository.get_session_detail("integration-missing-session", options)
    write_result = repository.save_sessions((_integration_row(),), options)

    _skip_if_integration_precondition_missing(
        list_result.error.kind if list_result.error is not None else None
    )
    _skip_if_integration_precondition_missing(
        detail_result.error.kind if detail_result.error is not None else None
    )
    _skip_if_integration_precondition_missing(
        write_result.error.kind if write_result.error is not None else None
    )

    assert list_result.ok is True
    assert detail_result.ok is True
    assert detail_result.dry_run is True
    assert write_result.ok is True
    assert write_result.dry_run is True

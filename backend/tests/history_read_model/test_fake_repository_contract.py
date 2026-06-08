from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from history_read_model.bigquery_schema import (
    COPILOT_SESSIONS_BASE_NAME,
    table_by_base_name,
)
from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
    ReadModelContractError,
)


def _valid_session_row() -> CopilotSessionRow:
    now = datetime(2026, 6, 8, 10, 30, tzinfo=UTC)
    return CopilotSessionRow(
        session_id="session-1",
        source_format="current",
        source_state="complete",
        created_at_source=now,
        updated_at_source=now,
        source_partition_date=date(2026, 6, 8),
        cwd="/workspace",
        git_root="/workspace",
        repository="repo",
        branch="main",
        selected_model="gpt-5",
        event_count=3,
        message_snapshot_count=2,
        issue_count=1,
        message_count=2,
        activity_count=4,
        degraded=False,
        conversation_preview="preview",
        source_paths={"primary": "/workspace/session.json"},
        source_fingerprint={"sha256": "abc"},
        summary_payload={"id": "session-1"},
        detail_payload={"messages": []},
        search_text="preview body",
        search_text_version=1,
        indexed_at=now,
    )


def _valid_sync_run_row() -> HistorySyncRunRow:
    started_at = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
    finished_at = datetime(2026, 6, 8, 10, 1, tzinfo=UTC)
    return HistorySyncRunRow(
        sync_run_id="sync-1",
        status="succeeded",
        started_at=started_at,
        finished_at=finished_at,
        started_partition_date=date(2026, 6, 8),
        processed_count=3,
        inserted_count=1,
        updated_count=2,
        saved_count=3,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key=None,
        indexed_at=finished_at,
    )


# 概要・目的: fake repository が BigQuery 実接続なしで valid session row を保存できることを守る。
# テストケース: schema 契約を満たす CopilotSessionRow を save_session して session_id で取得する。
# 期待値: BigQuery client や dataset に触れず、in-memory に保存済み row が返る。
def test_fake_repository_saves_valid_session_rows_in_memory() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = _valid_session_row()

    repository.save_session(row)

    assert repository.get_session("session-1") == row
    assert repository.list_sessions() == (row,)


# 概要・目的: fake repository が session enum と count invariant の保存契約を検証することを守る。
# テストケース: source_format の不正値と負数 count を含む row を save_session する。
# 期待値: schema の allowed_values / non_negative 由来の契約違反として失敗する。
def test_fake_repository_rejects_invalid_session_enum_and_negative_count() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = replace(_valid_session_row(), source_format="future", event_count=-1)

    with pytest.raises(ReadModelContractError) as error:
        repository.save_session(row)

    assert "copilot_sessions.source_format must be one of" in str(error.value)
    assert "copilot_sessions.event_count must be non-negative" in str(error.value)
    assert repository.get_session("session-1") is None


# 概要・目的: fake repository が JSON payload object と search version 契約を守る。
# テストケース: summary_payload を list にし、search_text_version を負数にした row を保存する。
# 期待値: presenter payload を再定義せず JSON object / 非負 version の契約違反として失敗する。
def test_fake_repository_rejects_invalid_payload_object_and_search_version() -> None:
    repository = FakeBigQueryReadModelRepository()
    invalid_payload = cast(Mapping[str, object], [])
    row = replace(
        _valid_session_row(),
        summary_payload=invalid_payload,
        search_text=cast(str, None),
        search_text_version=-1,
    )

    with pytest.raises(ReadModelContractError) as error:
        repository.save_session(row)

    assert "copilot_sessions.summary_payload must be a JSON object mapping" in str(error.value)
    assert "copilot_sessions.search_text is required" in str(error.value)
    assert "copilot_sessions.search_text_version must be non-negative" in str(error.value)


# 概要・目的: fake repository が valid sync run row と lifecycle invariant を保存できることを守る。
# テストケース: terminal status で saved_count が inserted_count + updated_count と一致する。
# 期待値: sync_run_id で取得でき、保存集計の lifecycle contract が維持される。
def test_fake_repository_saves_valid_sync_run_rows_in_memory() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = _valid_sync_run_row()

    repository.save_sync_run(row)

    assert repository.get_sync_run("sync-1") == row
    assert repository.list_sync_runs() == (row,)


# 概要・目的: fake repository が sync lifecycle と saved count invariant の違反を拒否する。
# テストケース: terminal status で finished_at を欠落させ、saved_count を不一致にする。
# 期待値: BigQuery へ接続せず、schema 契約違反として失敗する。
def test_fake_repository_rejects_invalid_sync_lifecycle_and_saved_count() -> None:
    repository = FakeBigQueryReadModelRepository()
    enum_row = replace(_valid_sync_run_row(), status=cast(Any, "future"))

    with pytest.raises(ReadModelContractError) as enum_error:
        repository.save_sync_run(enum_row)

    assert "history_sync_runs.status must be one of" in str(enum_error.value)

    row = replace(_valid_sync_run_row(), finished_at=None, saved_count=4)

    with pytest.raises(ReadModelContractError) as error:
        repository.save_sync_run(row)

    assert "history_sync_runs.finished_at is required for terminal status" in str(error.value)
    assert "history_sync_runs.saved_count must equal inserted_count + updated_count" in str(
        error.value
    )
    assert repository.get_sync_run("sync-1") is None


# 概要・目的: fake repository が running sync の lock identity 契約を検証することを守る。
# テストケース: running status で running_lock_key が欠落した row を保存する。
# 期待値: running 中の競合判定に必要な lock identity 欠落として失敗する。
def test_fake_repository_rejects_running_sync_run_without_lock_key() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = replace(_valid_sync_run_row(), status="running", finished_at=None, running_lock_key=None)

    with pytest.raises(ReadModelContractError) as error:
        repository.save_sync_run(row)

    assert "history_sync_runs.running_lock_key is required for running status" in str(error.value)


# 概要・目的: fake repository が SchemaDefinition と row contract の drift を検出する。
# テストケース: schema required field に custom table で追加列を足して fake に渡す。
# 期待値: row contract が schema required fields を満たさない場合、保存前に契約違反として失敗する。
def test_fake_repository_detects_required_field_drift_from_schema_definition() -> None:
    sessions_table = table_by_base_name(COPILOT_SESSIONS_BASE_NAME)
    drifted_sessions_table = replace(
        sessions_table,
        columns=(
            *sessions_table.columns,
            sessions_table.column_map["source_format"].__class__(
                name="new_required_field",
                type="STRING",
                mode="REQUIRED",
                default_equivalent=None,
                description="Artificial required field used to prove drift detection.",
            ),
        ),
    )
    sync_runs_table = table_by_base_name("history_sync_runs")
    repository = FakeBigQueryReadModelRepository(
        schema_tables=(drifted_sessions_table, sync_runs_table)
    )

    with pytest.raises(ReadModelContractError) as error:
        repository.save_session(_valid_session_row())

    assert "copilot_sessions.new_required_field is required by schema but missing from row" in str(
        error.value
    )

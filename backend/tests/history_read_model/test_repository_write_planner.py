from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime

from history_read_model.fake_repository import CopilotSessionRow
from history_read_model.repository_write_planner import (
    ExistingSessionMetadata,
    InvalidSessionWriteInput,
    WorkspaceOnlySessionWriteInput,
    plan_sync_write,
)

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)


def _row(
    session_id: str,
    *,
    fingerprint: Mapping[str, object] | None = None,
    search_text_version: int = 2,
    source_state: str = "complete",
    degraded: bool = False,
) -> CopilotSessionRow:
    return CopilotSessionRow(
        session_id=session_id,
        source_format="current",
        source_state=source_state,
        created_at_source=datetime(2026, 6, 8, 9, 0, tzinfo=UTC),
        updated_at_source=datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        source_partition_date=date(2026, 6, 9),
        cwd=f"/workspace/{session_id}",
        git_root=f"/workspace/{session_id}",
        repository="octo/example",
        branch="feature/bigquery",
        selected_model="gpt-5",
        event_count=2,
        message_snapshot_count=0,
        issue_count=1 if degraded else 0,
        message_count=2,
        activity_count=0,
        degraded=degraded,
        conversation_preview="hello",
        source_paths={"events": f"/tmp/{session_id}.jsonl"},
        source_fingerprint=fingerprint or {"sha256": session_id},
        summary_payload={"id": session_id},
        detail_payload={"id": session_id, "issues": []},
        search_text=f"hello {session_id}",
        search_text_version=search_text_version,
        indexed_at=NOW,
    )


# 概要・目的: 新規 / 更新 / skip / workspace only / invalid の保存分類契約を守る。
# テストケース: 既存 metadata と入力候補を混在させて sync write plan を作る。
# 期待値: insert/update/skip/workspace_only/invalid が分離され、
# 保存対象外 row は MERGE 対象に入らない。
def test_plan_sync_write_classifies_rows_from_existing_metadata() -> None:
    same_fingerprint = {"sha256": "same"}
    inserted = _row("inserted")
    updated = _row("updated", fingerprint={"sha256": "new"})
    skipped = _row("skipped", fingerprint=same_fingerprint)
    workspace_only = WorkspaceOnlySessionWriteInput(session_id="workspace-only")
    invalid = InvalidSessionWriteInput(
        session_id="invalid",
        error_reasons=("created_at or updated_at is required",),
    )
    existing = {
        "updated": ExistingSessionMetadata(
            session_id="updated",
            source_fingerprint={"sha256": "old"},
            search_text_version=2,
        ),
        "skipped": ExistingSessionMetadata(
            session_id="skipped",
            source_fingerprint=same_fingerprint,
            search_text_version=2,
        ),
    }

    plan = plan_sync_write(
        (inserted, updated, skipped, workspace_only, invalid),
        existing_metadata=existing,
    )

    assert plan.insert_rows == (inserted,)
    assert plan.update_rows == (updated,)
    assert plan.skipped_session_ids == ("skipped",)
    assert plan.workspace_only_session_ids == ("workspace-only",)
    assert plan.invalid_rows == (invalid,)
    assert plan.rows_for_merge == (inserted, updated)


# 概要・目的: fingerprint が同じでも検索 projection version が古い row は更新対象にする。
# テストケース: 既存 metadata の source_fingerprint は一致するが search_text_version が古い。
# 期待値: update に分類され、skip と誤判定しない。
def test_plan_sync_write_updates_when_search_projection_version_differs() -> None:
    fingerprint = {"sha256": "same"}
    row = _row("projection-stale", fingerprint=fingerprint, search_text_version=2)

    plan = plan_sync_write(
        (row,),
        existing_metadata={
            "projection-stale": ExistingSessionMetadata(
                session_id="projection-stale",
                source_fingerprint=fingerprint,
                search_text_version=1,
            )
        },
    )

    assert plan.update_rows == (row,)
    assert plan.skipped_session_ids == ()


# 概要・目的: count invariant を BigQuery job statistics に依存せず planner が算出する契約を守る。
# テストケース: insert/update/skip/workspace_only/invalid/degraded を含む入力で
# result counts を確認する。
# 期待値: processed、inserted、updated、saved、skipped、failed、degraded が設計どおりになる。
def test_plan_sync_write_calculates_count_invariants_without_job_statistics() -> None:
    inserted = _row("inserted")
    updated = _row("updated", fingerprint={"sha256": "new"}, degraded=True)
    skipped_degraded = _row("skipped", fingerprint={"sha256": "same"}, degraded=True)
    invalid_degraded = replace(_row("invalid", degraded=True), session_id="")
    existing = {
        "updated": ExistingSessionMetadata(
            session_id="updated",
            source_fingerprint={"sha256": "old"},
            search_text_version=2,
        ),
        "skipped": ExistingSessionMetadata(
            session_id="skipped",
            source_fingerprint={"sha256": "same"},
            search_text_version=2,
        ),
    }

    plan = plan_sync_write(
        (
            inserted,
            updated,
            skipped_degraded,
            WorkspaceOnlySessionWriteInput(session_id="workspace-only"),
            InvalidSessionWriteInput(
                session_id="invalid",
                row=invalid_degraded,
                error_reasons=("session_id is required",),
            ),
        ),
        existing_metadata=existing,
    )

    result = plan.to_result()

    assert result.ok is True
    assert result.processed_count == 5
    assert result.inserted_count == 1
    assert result.updated_count == 1
    assert result.saved_count == 2
    assert result.skipped_count == 2
    assert result.failed_count == 1
    assert result.degraded_count == 2


# 概要・目的: row contract 違反を invalid として扱い、job-level error と混ぜない契約を守る。
# テストケース: source_format の不正値と負数 count を持つ row を planner に渡す。
# 期待値: invalid_rows に分類され、SyncWriteResult.error は設定されず failed_count だけが増える。
def test_plan_sync_write_classifies_schema_contract_violations_as_invalid_rows() -> None:
    invalid_row = replace(_row("invalid"), source_format="future", event_count=-1)

    plan = plan_sync_write((invalid_row,), existing_metadata={})
    result = plan.to_result()

    assert plan.insert_rows == ()
    assert plan.invalid_rows[0].session_id == "invalid"
    assert "copilot_sessions.source_format must be one of" in plan.invalid_rows[0].error_reasons[0]
    assert result.ok is True
    assert result.error is None
    assert result.failed_count == 1

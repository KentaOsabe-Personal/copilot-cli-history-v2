from __future__ import annotations

from datetime import UTC, datetime

from copilot_history.types import (
    NormalizedEvent,
    NormalizedSession,
    ReadIssue,
    ReadSuccessResult,
    ResolvedHistoryRoot,
)
from history_api.sync_rows import assemble_sync_rows

INDEXED_AT = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 6, 9, 12, 0, 2, tzinfo=UTC)


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
    created_at: datetime | None = datetime(2026, 6, 9, 9, 0, tzinfo=UTC),
    updated_at: datetime | None = datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
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
        created_at=created_at,
        updated_at=updated_at,
        selected_model="gpt-5",
        events=(_event(),),
        message_snapshots=(),
        issues=issues,
        source_paths={"events": f"/tmp/{session_id}.jsonl"},
    )


def _reader_result(*sessions: NormalizedSession) -> ReadSuccessResult:
    return ReadSuccessResult(
        root=ResolvedHistoryRoot(
            requested_root="/tmp/copilot",
            current_root="/tmp/copilot/session-state",
            legacy_root="/tmp/copilot/history-session-state",
        ),
        sessions=sessions,
    )


# 概要・目的: reader result から同期保存対象 row と分類別件数を組み立てる契約を守る。
# テストケース: persistable、workspace_only、invalid、degraded の session を含む
# reader result を変換する。
# 期待値: 保存対象は persistable のみ、workspace-only は skipped、invalid は failed、
# degraded は degraded_count に反映される。
def test_assemble_sync_rows_counts_session_classifications() -> None:
    issue = ReadIssue(
        code="event.partial",
        message="event was partially mapped",
        severity="warning",
        source_path="/tmp/degraded.jsonl",
        sequence=1,
    )

    assembly = assemble_sync_rows(
        _reader_result(
            _session("complete-session"),
            _session("workspace-only", source_state="workspace_only"),
            _session("invalid-session", created_at=None, updated_at=None),
            _session("degraded-session", source_state="degraded", issues=(issue,)),
        ),
        sync_run_id="101",
        started_at=INDEXED_AT,
        finished_at=FINISHED_AT,
        indexed_at=INDEXED_AT,
        write_processed_count=2,
        write_inserted_count=1,
        write_updated_count=1,
        write_skipped_count=0,
        write_failed_count=0,
    )

    assert [row.session_id for row in assembly.session_rows] == [
        "complete-session",
        "degraded-session",
    ]
    assert assembly.counts.processed_count == 4
    assert assembly.counts.inserted_count == 1
    assert assembly.counts.updated_count == 1
    assert assembly.counts.saved_count == 2
    assert assembly.counts.skipped_count == 1
    assert assembly.counts.failed_count == 1
    assert assembly.counts.degraded_count == 1
    assert assembly.invalid_failures == {
        "invalid-session": ("created_at or updated_at is required",)
    }


# 概要・目的: sync run row に lifecycle 時刻、status、counts、failure/degradation summary
# を反映する。
# テストケース: invalid と degraded を含む assembly から completed_with_issues の
# sync run row を作る。
# 期待値: terminal row は finished_at と counts を保持し、running lock は解除され summary が残る。
def test_assemble_sync_rows_builds_terminal_sync_run_row() -> None:
    issue = ReadIssue(
        code="event.partial",
        message="event was partially mapped",
        severity="warning",
        source_path="/tmp/degraded.jsonl",
        sequence=1,
    )

    assembly = assemble_sync_rows(
        _reader_result(
            _session("invalid-session", created_at=None, updated_at=None),
            _session("degraded-session", source_state="degraded", issues=(issue,)),
        ),
        sync_run_id="102",
        started_at=INDEXED_AT,
        finished_at=FINISHED_AT,
        indexed_at=INDEXED_AT,
        write_processed_count=1,
        write_inserted_count=1,
        write_updated_count=0,
        write_skipped_count=0,
        write_failed_count=0,
    )

    row = assembly.sync_run_row

    assert row.sync_run_id == "102"
    assert row.status == "completed_with_issues"
    assert row.started_at == INDEXED_AT
    assert row.finished_at == FINISHED_AT
    assert row.started_partition_date == INDEXED_AT.date()
    assert row.processed_count == 2
    assert row.inserted_count == 1
    assert row.updated_count == 0
    assert row.saved_count == 1
    assert row.skipped_count == 0
    assert row.failed_count == 1
    assert row.degraded_count == 1
    assert row.failure_summary == "1 session failed validation"
    assert row.degradation_summary == "1 session degraded"
    assert row.running_lock_key is None
    assert row.indexed_at == INDEXED_AT


# 概要・目的: repository write planner が返す skip / failure 件数を sync counts に反映する。
# テストケース: persistable 2 件のうち repository 側で 1 件 skip、1 件 failed として集計する。
# 期待値: workspace-only 分類とは別に write_skipped_count と write_failed_count が加算される。
def test_assemble_sync_rows_includes_repository_write_counts() -> None:
    assembly = assemble_sync_rows(
        _reader_result(_session("updated-session"), _session("skipped-session")),
        sync_run_id="103",
        started_at=INDEXED_AT,
        finished_at=FINISHED_AT,
        indexed_at=INDEXED_AT,
        write_processed_count=2,
        write_inserted_count=0,
        write_updated_count=1,
        write_skipped_count=1,
        write_failed_count=1,
    )

    assert assembly.counts.processed_count == 2
    assert assembly.counts.inserted_count == 0
    assert assembly.counts.updated_count == 1
    assert assembly.counts.saved_count == 1
    assert assembly.counts.skipped_count == 1
    assert assembly.counts.failed_count == 1
    assert assembly.sync_run_row.status == "completed_with_issues"

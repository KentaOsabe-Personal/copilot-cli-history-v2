from datetime import UTC, datetime

from copilot_history.types import NormalizedEvent, NormalizedSession, ReadIssue
from history_read_model.repository_rows import (
    SessionRowBuildStatus,
    build_copilot_session_write_input,
)


def _event(*, sequence: int, content: str = "hello") -> NormalizedEvent:
    return NormalizedEvent(
        sequence=sequence,
        kind="message",
        mapping_status="complete",
        raw_type="user.message",
        occurred_at=datetime(2026, 6, 9, 10, sequence, tzinfo=UTC),
        role="user",
        content=content,
        tool_calls=(),
        detail={},
        raw_payload={"type": "user.message"},
    )


def _session(
    *,
    session_id: str = "session-1",
    source_state: str = "complete",
    created_at: datetime | None = datetime(2026, 6, 8, 9, 0, tzinfo=UTC),
    updated_at: datetime | None = datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
    issues: tuple[ReadIssue, ...] = (),
) -> NormalizedSession:
    return NormalizedSession(
        session_id=session_id,
        source_format="current",
        source_state=source_state,  # type: ignore[arg-type]
        cwd="/workspace/session-1",
        git_root="/workspace/session-1",
        repository="octo/example",
        branch="feature/bigquery",
        created_at=created_at,
        updated_at=updated_at,
        selected_model="gpt-5",
        events=(_event(sequence=1, content="hello"), _event(sequence=2, content="answer")),
        message_snapshots=(),
        issues=issues,
        source_paths={"events": "/tmp/events.jsonl", "workspace": "/tmp/workspace.yaml"},
    )


# 概要・目的: normalized session から schema 保存 row と presenter payload を組み立てる境界を守る。
# テストケース: updated_at を持つ current session を source_fingerprint と indexed_at
# 付きで変換する。
# 期待値: row は BigQuery schema field を満たし、summary/detail payload は presenter
# 由来の shape を保持する。
def test_build_copilot_session_write_input_maps_session_to_persistable_row() -> None:
    indexed_at = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    fingerprint = {"complete": True, "artifacts": {"events": {"status": "ok"}}}

    candidate = build_copilot_session_write_input(
        _session(),
        source_fingerprint=fingerprint,
        indexed_at=indexed_at,
    )

    assert candidate.status == "persistable"
    assert candidate.row is not None
    assert candidate.row.session_id == "session-1"
    assert candidate.row.source_partition_date.isoformat() == "2026-06-09"
    assert candidate.row.source_fingerprint is fingerprint
    assert candidate.row.summary_payload["id"] == "session-1"
    assert candidate.row.detail_payload["id"] == "session-1"
    assert candidate.row.search_text_version == 2
    assert "hello" in candidate.row.search_text
    assert "/workspace/session-1" not in candidate.row.search_text
    assert candidate.row.indexed_at == indexed_at


# 概要・目的: workspace only session を表示用 read model の保存対象から外す分類契約を守る。
# テストケース: source_state が workspace_only の normalized session を保存入力に変換する。
# 期待値: row は作られず、repository write の前段で workspace_only として識別できる。
def test_build_copilot_session_write_input_classifies_workspace_only_without_row() -> None:
    candidate = build_copilot_session_write_input(
        _session(source_state="workspace_only"),
        source_fingerprint={"complete": True},
        indexed_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )

    assert candidate.status == "workspace_only"
    assert candidate.row is None
    assert candidate.session_id == "session-1"


# 概要・目的: degraded 状態と issue 情報が保存 payload から失われないことを守る。
# テストケース: session-level issue を持つ degraded session を保存入力に変換する。
# 期待値: row の degraded / issue_count と summary/detail payload の issues が
# 後続表示で識別可能に残る。
def test_build_copilot_session_write_input_preserves_degraded_payload_issues() -> None:
    issue = ReadIssue(
        code="workspace.unreadable",
        message="workspace metadata is not accessible",
        severity="warning",
        source_path="/tmp/workspace.yaml",
        sequence=None,
    )

    candidate = build_copilot_session_write_input(
        _session(source_state="degraded", issues=(issue,)),
        source_fingerprint={"complete": False},
        indexed_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )

    assert candidate.status == "persistable"
    assert candidate.row is not None
    assert candidate.row.degraded is True
    assert candidate.row.issue_count == 1
    assert candidate.row.summary_payload["degraded"] is True
    assert candidate.row.detail_payload["degraded"] is True
    assert candidate.row.detail_payload["issues"] == [
        {
            "code": "workspace.unreadable",
            "severity": "warning",
            "message": "workspace metadata is not accessible",
            "source_path": "/tmp/workspace.yaml",
            "scope": "session",
            "event_sequence": None,
        }
    ]


# 概要・目的: schema 契約に必要な partition date を作れない session を保存前に invalid 分類する。
# テストケース: created_at と updated_at がどちらも欠落した session を保存入力に変換する。
# 期待値: row は作られず、invalid と理由が返り BigQuery write 対象から外せる。
def test_build_copilot_session_write_input_rejects_missing_display_time() -> None:
    candidate = build_copilot_session_write_input(
        _session(created_at=None, updated_at=None),
        source_fingerprint={"complete": True},
        indexed_at=datetime(2026, 6, 9, 12, 0, tzinfo=UTC),
    )

    assert candidate.status == "invalid"
    assert candidate.row is None
    assert candidate.error_reasons == ("created_at or updated_at is required",)


# 概要・目的: 保存入力の分類 status が想定値だけで型付けされることを守る。
# テストケース: SessionRowBuildStatus として許可された status の tuple を作る。
# 期待値: persistable、workspace_only、invalid の 3 分類を扱える。
def test_session_row_build_status_type_covers_expected_classifications() -> None:
    statuses: tuple[SessionRowBuildStatus, ...] = ("persistable", "workspace_only", "invalid")

    assert statuses == ("persistable", "workspace_only", "invalid")

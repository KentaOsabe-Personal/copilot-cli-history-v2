from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.types import (
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    ReadIssue,
)
from history_read_model.repository_rows import (
    SessionRowBuildStatus,
    build_copilot_session_write_input,
)

OCCURRED_AT = datetime(2026, 6, 9, 10, tzinfo=UTC)


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


def _session_with_raw_payload() -> NormalizedSession:
    raw_payload = {
        "type": "assistant.message",
        "secret_raw_only_value": "do-not-index-this-raw-json",
        "data": {"content": "visible assistant message"},
    }
    return NormalizedSession(
        session_id="raw-session",
        source_format="current",
        source_state="complete",
        cwd="/workspace",
        git_root="/workspace",
        repository="repo",
        branch="main",
        created_at=OCCURRED_AT,
        updated_at=OCCURRED_AT,
        selected_model="gpt-5",
        events=(
            NormalizedEvent(
                sequence=1,
                kind="message",
                mapping_status="complete",
                raw_type="assistant.message",
                occurred_at=OCCURRED_AT,
                role="assistant",
                content="visible assistant message",
                tool_calls=(),
                detail={},
                raw_payload=raw_payload,
            ),
        ),
        message_snapshots=(
            MessageSnapshot(
                sequence=1,
                role="assistant",
                content="visible assistant message",
                occurred_at=OCCURRED_AT,
                raw_payload=raw_payload,
            ),
        ),
        issues=(),
        source_paths={"events": "/tmp/events.jsonl"},
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


# 概要・目的: read model の詳細 payload が後続 API raw opt-in を再現できることを守る。
# テストケース: raw payload を持つ normalized session から repository row を組み立てる。
# 期待値: 保存される detail_payload は raw_included=true と raw_payload 実値を保持する。
def test_build_copilot_session_write_input_stores_raw_capable_detail_payload() -> None:
    candidate = build_copilot_session_write_input(
        _session_with_raw_payload(),
        source_fingerprint={"sha256": "raw-session"},
        indexed_at=OCCURRED_AT,
    )

    assert candidate.row is not None
    detail_payload = candidate.row.detail_payload
    message_snapshots = cast(list[dict[str, Any]], detail_payload["message_snapshots"])

    assert detail_payload["raw_included"] is True
    assert message_snapshots[0]["raw_payload"] == {
        "type": "assistant.message",
        "secret_raw_only_value": "do-not-index-this-raw-json",
        "data": {"content": "visible assistant message"},
    }


# 概要・目的: search projection が raw JSON 全文を検索対象に混ぜない契約を守る。
# テストケース: raw payload だけに存在する secret 値を含む session row を組み立てる。
# 期待値: search_text には表示用の会話本文だけが入り、raw-only 値は入らない。
def test_build_copilot_session_write_input_excludes_raw_only_values_from_search_text() -> None:
    candidate = build_copilot_session_write_input(
        _session_with_raw_payload(),
        source_fingerprint={"sha256": "raw-session"},
        indexed_at=OCCURRED_AT,
    )

    assert candidate.row is not None
    assert "visible assistant message" in candidate.row.search_text
    assert "do-not-index-this-raw-json" not in candidate.row.search_text

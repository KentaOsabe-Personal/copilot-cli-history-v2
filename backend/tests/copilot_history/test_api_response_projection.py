from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.api.presenters.issue_presenter import IssuePresenter
from copilot_history.api.response_projection import SessionResponseProjector
from copilot_history.types import (
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    NormalizedToolCall,
    ReadIssue,
)

OCCURRED_AT = datetime(2026, 4, 28, 4, 0, 1, tzinfo=UTC)


def _event(
    *,
    sequence: int,
    kind: str = "message",
    mapping_status: str = "complete",
    raw_type: str | None = "user.message",
    role: str | None = "user",
    content: str | None = "hello",
    tool_calls: tuple[NormalizedToolCall, ...] = (),
    detail: dict[str, object] | None = None,
    raw_payload: dict[str, object] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        sequence=sequence,
        kind=kind,  # type: ignore[arg-type]
        mapping_status=mapping_status,  # type: ignore[arg-type]
        raw_type=raw_type,
        occurred_at=OCCURRED_AT,
        role=role,
        content=content,
        tool_calls=tool_calls,
        detail=detail or {},
        raw_payload=raw_payload or {"type": raw_type, "data": {"content": content}},
    )


def _session(
    *,
    events: tuple[NormalizedEvent, ...],
    issues: tuple[ReadIssue, ...] = (),
    message_snapshots: tuple[MessageSnapshot, ...] = (),
    source_state: str = "complete",
) -> NormalizedSession:
    return NormalizedSession(
        session_id="session-1",
        source_format="current",
        source_state=source_state,  # type: ignore[arg-type]
        cwd="/workspace/session-1",
        git_root="/workspace/session-1",
        repository="octo/example",
        branch="feature/presenter",
        created_at=OCCURRED_AT,
        updated_at=OCCURRED_AT,
        selected_model="gpt-5",
        events=events,
        message_snapshots=message_snapshots,
        issues=issues,
        source_paths={"events": "/tmp/events.jsonl", "workspace": "/tmp/workspace.yaml"},
    )


# 概要・目的: reader issue を API issue envelope へ変換する契約を守る。
# テストケース: sequence なし issue と sequence あり issue を変換する。
# 期待値: code、severity、message、source_path は改名されず、scope と
# event_sequence だけが配置判断用に追加される。
def test_issue_presenter_preserves_issue_fields_and_assigns_scope() -> None:
    session_issue = ReadIssue(
        code="workspace.unreadable",
        message="workspace metadata is not accessible",
        severity="warning",
        source_path="/tmp/workspace.yaml",
        sequence=None,
    )
    event_issue = ReadIssue(
        code="event.partial",
        message="event was partially mapped",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=2,
    )

    presenter = IssuePresenter()

    assert presenter.present(session_issue) == {
        "code": "workspace.unreadable",
        "severity": "warning",
        "message": "workspace metadata is not accessible",
        "source_path": "/tmp/workspace.yaml",
        "scope": "session",
        "event_sequence": None,
    }
    assert presenter.present(event_issue) == {
        "code": "event.partial",
        "severity": "warning",
        "message": "event was partially mapped",
        "source_path": "/tmp/events.jsonl",
        "scope": "event",
        "event_sequence": 2,
    }


# 概要・目的: session 一覧 summary が frontend DTO の field set と
# current / legacy 共通 schema を維持する契約を守る。
# テストケース: 会話 event、tool call 付き assistant event、session issue を持つ
# degraded session から summary を生成する。
# 期待値: conversation summary、activity_count、degraded、issues が
# fixture と同じ意味の JSON serializable dict になる。
def test_project_summary_builds_api_summary_with_conversation_and_issues() -> None:
    issue = ReadIssue(
        code="workspace.unreadable",
        message="workspace metadata is not accessible",
        severity="warning",
        source_path="/tmp/workspace.yaml",
        sequence=None,
    )
    session = _session(
        events=(
            _event(sequence=1, content="first user message"),
            _event(
                sequence=2,
                raw_type="assistant.message",
                role="assistant",
                content="assistant answer",
                tool_calls=(
                    NormalizedToolCall(
                        name="apply_patch",
                        arguments_preview='{"cmd":"patch"}',
                        is_truncated=False,
                    ),
                ),
            ),
        ),
        issues=(issue,),
        source_state="degraded",
    )

    summary = SessionResponseProjector().project_summary(session)

    assert summary == {
        "id": "session-1",
        "source_format": "current",
        "created_at": "2026-04-28T04:00:01Z",
        "updated_at": "2026-04-28T04:00:01Z",
        "work_context": {
            "cwd": "/workspace/session-1",
            "git_root": "/workspace/session-1",
            "repository": "octo/example",
            "branch": "feature/presenter",
        },
        "selected_model": "gpt-5",
        "source_state": "degraded",
        "event_count": 2,
        "message_snapshot_count": 0,
        "conversation_summary": {
            "has_conversation": True,
            "message_count": 2,
            "preview": "first user message",
            "activity_count": 1,
        },
        "degraded": True,
        "issues": [
            {
                "code": "workspace.unreadable",
                "severity": "warning",
                "message": "workspace metadata is not accessible",
                "source_path": "/tmp/workspace.yaml",
                "scope": "session",
                "event_sequence": None,
            }
        ],
    }


# 概要・目的: session 詳細 projection が timeline / conversation / activity
# に event issue を sequence 単位で分配する契約を守る。
# テストケース: event issue を持つ partial assistant event から detail parts を生成する。
# 期待値: 該当 sequence の entry だけ degraded になり、tool call status、
# activity title / summary / source_path / raw_available が保持される。
def test_project_detail_distributes_event_issues_to_matching_entries() -> None:
    event_issue = ReadIssue(
        code="event.partial",
        message="tool call arguments were truncated",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=2,
    )
    session = _session(
        events=(
            _event(sequence=1, content="first user message"),
            _event(
                sequence=2,
                mapping_status="partial",
                raw_type="assistant.message",
                role="assistant",
                content="assistant answer",
                tool_calls=(
                    NormalizedToolCall(
                        name="apply_patch",
                        arguments_preview='{"cmd":"patch"}',
                        is_truncated=True,
                    ),
                ),
            ),
        ),
        issues=(event_issue,),
    )

    detail = SessionResponseProjector().project_detail(session, include_raw=False)
    conversation = cast(dict[str, Any], detail["conversation"])
    conversation_entries = cast(list[dict[str, Any]], conversation["entries"])
    activity = cast(dict[str, Any], detail["activity"])
    activity_entries = cast(list[dict[str, Any]], activity["entries"])
    timeline = cast(list[dict[str, Any]], detail["timeline"])

    assert conversation_entries[0]["degraded"] is False
    assistant_entry = conversation_entries[1]
    assert assistant_entry["degraded"] is True
    assert assistant_entry["tool_calls"] == [
        {
            "name": "apply_patch",
            "arguments_preview": '{"cmd":"patch"}',
            "is_truncated": True,
            "status": "partial",
        }
    ]
    activity_entry = activity_entries[0]
    assert activity_entry["title"] == "apply_patch"
    assert activity_entry["summary"] == '{"cmd":"patch"}'
    assert activity_entry["source_path"] == "/tmp/events.jsonl"
    assert activity_entry["raw_available"] is True
    assert activity_entry["degraded"] is True
    assert timeline[1]["issues"] == assistant_entry["issues"]
    assert timeline[1]["degraded"] is True


# 概要・目的: raw payload opt-in が response projection 内で一貫して
# 切り替わる契約を守る。
# テストケース: raw payload を持つ snapshot、activity、timeline を raw なしと
# raw 付きの両方で生成する。
# 期待値: raw_available は変わらず、差分は raw_included と raw_payload の
# null / 実値だけに限定される。
def test_project_detail_switches_raw_payloads_only_when_include_raw_is_enabled() -> None:
    raw_payload: dict[str, object] = {
        "type": "user.message",
        "data": {"content": "first user message"},
    }
    session = _session(
        events=(
            _event(
                sequence=1,
                raw_type="assistant.message",
                role="assistant",
                content="first assistant message",
                tool_calls=(
                    NormalizedToolCall(
                        name="apply_patch",
                        arguments_preview='{"cmd":"patch"}',
                        is_truncated=False,
                    ),
                ),
                raw_payload=raw_payload,
            ),
        ),
        message_snapshots=(
            MessageSnapshot(
                sequence=1,
                role="assistant",
                content="first assistant message",
                occurred_at=OCCURRED_AT,
                raw_payload=raw_payload,
            ),
        ),
    )
    projector = SessionResponseProjector()

    without_raw = projector.project_detail(session, include_raw=False)
    with_raw = projector.project_detail(session, include_raw=True)
    without_snapshots = cast(list[dict[str, Any]], without_raw["message_snapshots"])
    with_snapshots = cast(list[dict[str, Any]], with_raw["message_snapshots"])
    without_activity = cast(dict[str, Any], without_raw["activity"])
    with_activity = cast(dict[str, Any], with_raw["activity"])
    without_activity_entries = cast(list[dict[str, Any]], without_activity["entries"])
    with_activity_entries = cast(list[dict[str, Any]], with_activity["entries"])
    without_timeline = cast(list[dict[str, Any]], without_raw["timeline"])
    with_timeline = cast(list[dict[str, Any]], with_raw["timeline"])

    assert without_raw["raw_included"] is False
    assert with_raw["raw_included"] is True
    assert without_snapshots[0]["raw_payload"] is None
    assert with_snapshots[0]["raw_payload"] == raw_payload
    assert without_activity_entries[0]["raw_available"] is True
    assert with_activity_entries[0]["raw_available"] is True
    assert without_activity_entries[0]["raw_payload"] is None
    assert with_activity_entries[0]["raw_payload"] == raw_payload
    assert without_timeline[0]["raw_payload"] is None
    assert with_timeline[0]["raw_payload"] == raw_payload

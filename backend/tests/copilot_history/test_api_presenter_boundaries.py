from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.api.presenters import ErrorPresenter
from copilot_history.api.response_projection import SessionResponseProjector
from copilot_history.api.types import RootFailurePresentationInput, ValidationErrorPresentationInput
from copilot_history.types import NormalizedEvent, NormalizedSession, NormalizedToolCall, ReadIssue

OCCURRED_AT = datetime(2026, 5, 1, 10, 30, tzinfo=UTC)


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
        raw_payload=raw_payload or {},
    )


def _session(
    *,
    events: tuple[NormalizedEvent, ...],
    issues: tuple[ReadIssue, ...] = (),
    source_paths: dict[str, str] | None = None,
) -> NormalizedSession:
    return NormalizedSession(
        session_id="boundary-session",
        source_format="current",
        source_state="complete",
        cwd="/workspace/boundary",
        git_root="/workspace/boundary",
        repository="octo/example",
        branch="feature/presenter-boundary",
        created_at=OCCURRED_AT,
        updated_at=OCCURRED_AT,
        selected_model="gpt-5",
        events=events,
        message_snapshots=(),
        issues=issues,
        source_paths=source_paths or {},
    )


# 概要・目的: empty conversation と tool-only assistant を conversation / activity 境界で守る。
# テストケース: content を持たず tool call だけを持つ assistant message を詳細 projection に渡す。
# 期待値: conversation は空のまま、activity / timeline に tool call status と raw_available が残る。
def test_project_detail_keeps_tool_only_assistant_out_of_conversation() -> None:
    session = _session(
        events=(
            _event(
                sequence=1,
                raw_type="assistant.message",
                role="assistant",
                content=None,
                tool_calls=(
                    NormalizedToolCall(
                        name="functions.exec",
                        arguments_preview='{"cmd":"pwd"}',
                        is_truncated=False,
                    ),
                ),
                raw_payload={"type": "assistant.message"},
            ),
        ),
        source_paths={"events": "/tmp/events.jsonl"},
    )

    detail = SessionResponseProjector().project_detail(session, include_raw=False)
    conversation = cast(dict[str, Any], detail["conversation"])
    activity = cast(dict[str, Any], detail["activity"])
    activity_entries = cast(list[dict[str, Any]], activity["entries"])
    timeline = cast(list[dict[str, Any]], detail["timeline"])

    assert conversation["entries"] == []
    assert conversation["message_count"] == 0
    assert conversation["empty_reason"] == "no_conversation_messages"
    assert activity_entries[0]["category"] == "tool_call"
    assert activity_entries[0]["title"] == "functions.exec"
    assert activity_entries[0]["summary"] == '{"cmd":"pwd"}'
    assert activity_entries[0]["raw_available"] is True
    assert timeline[0]["tool_calls"][0]["status"] == "complete"


# 概要・目的: unknown / partial event の fallback 導出と issue 分配を小さい入力で守る。
# テストケース: source_paths を持たず event issue だけが source_path を持つ
# unknown partial event を渡す。
# 期待値: 読めた field は timeline / activity に残り、source_path と
# fallback title / summary が導出される。
def test_project_detail_preserves_unknown_partial_event_fallbacks_and_issue_source_path() -> None:
    issue = ReadIssue(
        code="event.partial_mapping",
        message="event payload matched partially",
        severity="warning",
        source_path="/tmp/fallback-events.jsonl",
        sequence=1,
    )
    session = _session(
        events=(
            _event(
                sequence=1,
                kind="unknown",
                mapping_status="partial",
                raw_type=None,
                role=None,
                content=None,
                raw_payload={},
            ),
        ),
        issues=(issue,),
    )

    detail = SessionResponseProjector().project_detail(session, include_raw=True)
    activity = cast(dict[str, Any], detail["activity"])
    activity_entries = cast(list[dict[str, Any]], activity["entries"])
    timeline = cast(list[dict[str, Any]], detail["timeline"])

    assert activity_entries == [
        {
            "sequence": 1,
            "category": "unknown",
            "title": "unknown event",
            "summary": None,
            "raw_type": None,
            "mapping_status": "partial",
            "occurred_at": "2026-05-01T10:30:00Z",
            "source_path": "/tmp/fallback-events.jsonl",
            "raw_available": False,
            "raw_payload": None,
            "degraded": True,
            "issues": [
                {
                    "code": "event.partial_mapping",
                    "severity": "warning",
                    "message": "event payload matched partially",
                    "source_path": "/tmp/fallback-events.jsonl",
                    "scope": "event",
                    "event_sequence": 1,
                }
            ],
        }
    ]
    assert timeline[0]["kind"] == "unknown"
    assert timeline[0]["mapping_status"] == "partial"
    assert timeline[0]["degraded"] is True


# 概要・目的: common error Presenter が details key を改名しない契約を守る。
# テストケース: not found、validation、root failure を小さい入力で生成する。
# 期待値: top-level error のみになり、session_id、field、reason、path key が保持される。
def test_error_presenter_preserves_common_error_detail_keys() -> None:
    presenter = ErrorPresenter()

    not_found = presenter.from_not_found(session_id="missing-session")
    validation = presenter.from_validation(
        ValidationErrorPresentationInput(
            code="invalid_session_list_query",
            message="session list query is invalid",
            details={"field": "limit", "reason": "too_large"},
        )
    )
    root_failure = presenter.from_root_failure(
        RootFailurePresentationInput(
            code="root_unreadable",
            message="history root is not readable",
            path="/tmp/unreadable/.copilot",
        )
    )

    assert set(not_found) == {"error"}
    not_found_error = cast(dict[str, Any], not_found["error"])
    validation_error = cast(dict[str, Any], validation["error"])
    root_failure_error = cast(dict[str, Any], root_failure["error"])
    assert not_found_error["details"] == {"session_id": "missing-session"}
    assert validation_error["details"] == {
        "field": "limit",
        "reason": "too_large",
    }
    assert root_failure_error["details"] == {"path": "/tmp/unreadable/.copilot"}

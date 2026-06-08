from datetime import UTC, datetime

from copilot_history.projections import (
    ActivityProjector,
    ConversationProjector,
    SearchTextProjector,
)
from copilot_history.types import (
    NormalizedEvent,
    NormalizedSession,
    NormalizedToolCall,
    ReadIssue,
)


def _session_with_events(
    events: tuple[NormalizedEvent, ...],
    issues: tuple[ReadIssue, ...] = (),
) -> NormalizedSession:
    return NormalizedSession(
        session_id="projection-session",
        source_format="current",
        source_state="degraded" if issues else "complete",
        cwd="/workspace/app",
        git_root=None,
        repository=None,
        branch=None,
        created_at=None,
        updated_at=None,
        selected_model=None,
        events=events,
        message_snapshots=(),
        issues=issues,
        source_paths={"events": "/tmp/events.jsonl"},
    )


# 概要・目的: user / assistant の非空本文 message を conversation entry として返す。
# テストケース: user、system、assistant の message event を source order で含む session を投影する。
# 期待値: user と assistant だけが順序を保って entries に入り、summary preview が生成される。
def test_conversation_projector_returns_non_empty_user_and_assistant_messages() -> None:
    occurred_at = datetime(2026, 6, 8, 1, 0, tzinfo=UTC)
    session = _session_with_events(
        (
            NormalizedEvent(
                sequence=1,
                kind="message",
                mapping_status="complete",
                raw_type="user.message",
                occurred_at=occurred_at,
                role="user",
                content="最初の依頼",
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
            NormalizedEvent(
                sequence=2,
                kind="message",
                mapping_status="complete",
                raw_type="system.message",
                occurred_at=occurred_at,
                role="system",
                content="system note",
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
            NormalizedEvent(
                sequence=3,
                kind="message",
                mapping_status="complete",
                raw_type="assistant.message",
                occurred_at=occurred_at,
                role="assistant",
                content="回答",
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
        )
    )

    projection = ConversationProjector().project(session)

    assert [(entry.sequence, entry.role, entry.content) for entry in projection.entries] == [
        (1, "user", "最初の依頼"),
        (3, "assistant", "回答"),
    ]
    assert projection.summary.message_count == 2
    assert projection.summary.preview == "最初の依頼"
    assert projection.summary.empty_reason is None


# 概要・目的: assistant の tool-only event を空 conversation entry にしない契約を守る。
# テストケース: content を持たず tool call だけを持つ assistant message を投影する。
# 期待値: conversation は空で、tool context は activity projection から参照できる。
def test_tool_only_assistant_message_is_activity_not_empty_conversation() -> None:
    session = _session_with_events(
        (
            NormalizedEvent(
                sequence=1,
                kind="message",
                mapping_status="complete",
                raw_type="assistant.message",
                occurred_at=None,
                role="assistant",
                content=None,
                tool_calls=(
                    NormalizedToolCall(
                        name="functions.exec",
                        arguments_preview='{"cmd":"pwd"}',
                        is_truncated=False,
                        raw_payload={},
                    ),
                ),
                detail={},
                raw_payload={},
            ),
        )
    )

    conversation = ConversationProjector().project(session)
    activity = ActivityProjector().project(session)

    assert conversation.entries == ()
    assert conversation.summary.message_count == 0
    assert conversation.summary.empty_reason == "no_conversation_messages"
    assert [(entry.sequence, entry.category, entry.body) for entry in activity.entries] == [
        (1, "tool_call", 'functions.exec {"cmd":"pwd"}')
    ]


# 概要・目的: system、detail、unknown、非会話 event を activity として区別する。
# テストケース: system message、tool detail、unknown event を含む session を投影する。
# 期待値: activity entries が category と body を保持し、conversation と分離される。
def test_activity_projector_classifies_non_conversation_events() -> None:
    session = _session_with_events(
        (
            NormalizedEvent(
                sequence=1,
                kind="message",
                mapping_status="complete",
                raw_type="system.message",
                occurred_at=None,
                role="system",
                content="system note",
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
            NormalizedEvent(
                sequence=2,
                kind="detail",
                mapping_status="complete",
                raw_type="tool.execution_complete",
                occurred_at=None,
                role=None,
                content=None,
                tool_calls=(),
                detail={"category": "tool_execution", "body": "functions.exec / call-1"},
                raw_payload={},
            ),
            NormalizedEvent(
                sequence=3,
                kind="unknown",
                mapping_status="complete",
                raw_type="mystery.event",
                occurred_at=None,
                role=None,
                content=None,
                tool_calls=(),
                detail={},
                raw_payload={"type": "mystery.event"},
            ),
        )
    )

    projection = ActivityProjector().project(session)

    assert [(entry.sequence, entry.category, entry.body) for entry in projection.entries] == [
        (1, "system", "system note"),
        (2, "tool_execution", "functions.exec / call-1"),
        (3, "unknown", "mystery.event"),
    ]


# 概要・目的: search projection が会話本文、preview、issue message を基礎情報として返す。
# テストケース: conversation event と read issue を持つ session を SearchTextProjector に渡す。
# 期待値: ranking や外部 index 情報を持たない SearchTextSource.parts が生成される。
def test_search_text_projector_collects_conversation_preview_and_issue_text() -> None:
    issue = ReadIssue(
        code="event.unknown_shape",
        message="unknown event shape",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=2,
    )
    session = _session_with_events(
        (
            NormalizedEvent(
                sequence=1,
                kind="message",
                mapping_status="complete",
                raw_type="user.message",
                occurred_at=None,
                role="user",
                content="検索対象の本文",
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
        ),
        issues=(issue,),
    )

    search = SearchTextProjector().project(session)

    assert search.parts == ("検索対象の本文", "unknown event shape")
    assert not hasattr(search, "score")
    assert not hasattr(search, "index_name")

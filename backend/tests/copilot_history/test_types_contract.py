from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from copilot_history.types import (
    ActivityEntry,
    ActivityProjection,
    ConversationEntry,
    ConversationProjection,
    ConversationSummary,
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    ReadFailureResult,
    ReadIssue,
    ReadSuccessResult,
    ResolvedHistoryRoot,
    SearchTextSource,
)


# 概要・目的: normalized session contract が session 内容から
# count と degraded state を導出する契約を守る。
# テストケース: event、message snapshot、issue を持つ degraded session を生成する。
# 期待値: count property は tuple 長から導出され、
# source_state=degraded のときだけ degraded が true になる。
def test_normalized_session_derives_counts_and_degraded_state() -> None:
    occurred_at = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)
    event = NormalizedEvent(
        sequence=1,
        kind="message",
        mapping_status="complete",
        raw_type="user.message",
        occurred_at=occurred_at,
        role="user",
        content="reader を実装して",
        tool_calls=(),
        detail={},
        raw_payload={"type": "user.message"},
    )
    snapshot = MessageSnapshot(
        sequence=1,
        role="user",
        content="reader を実装して",
        occurred_at=occurred_at,
        raw_payload={"role": "user"},
    )
    issue = ReadIssue(
        code="event.unknown_shape",
        message="unknown event shape",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=2,
    )

    session = NormalizedSession(
        session_id="current-valid",
        source_format="current",
        source_state="degraded",
        cwd="/workspace/app",
        git_root="/workspace/app",
        repository="copilot-cli-history-v2",
        branch="main",
        created_at=occurred_at,
        updated_at=occurred_at,
        selected_model="gpt-5",
        events=(event,),
        message_snapshots=(snapshot,),
        issues=(issue,),
        source_paths={"workspace": "/tmp/workspace.yaml", "events": "/tmp/events.jsonl"},
    )

    assert session.event_count == 1
    assert session.message_snapshot_count == 1
    assert session.issue_count == 1
    assert session.degraded is True


# 概要・目的: dataclass contract が immutable value として扱える境界を守る。
# テストケース: normalized session の field 代入と source_paths の直接変更を試す。
# 期待値: frozen dataclass と read-only mapping により、どちらも変更できない。
def test_normalized_session_is_immutable_and_freezes_source_paths() -> None:
    session = NormalizedSession(
        session_id="legacy-valid",
        source_format="legacy",
        source_state="complete",
        cwd=None,
        git_root=None,
        repository=None,
        branch=None,
        created_at=None,
        updated_at=None,
        selected_model=None,
        events=(),
        message_snapshots=(),
        issues=(),
        source_paths={"legacy": "/tmp/legacy.json"},
    )

    with pytest.raises(FrozenInstanceError):
        session.session_id = "changed"  # type: ignore[misc]

    with pytest.raises(TypeError):
        cast(MutableMapping[str, str], session.source_paths)["legacy"] = "/tmp/changed.json"


# 概要・目的: enum 相当の public fields が仕様外の値を受け付けない契約を守る。
# テストケース: source_format、source_state、event kind、mapping status、severity に不正値を渡す。
# 期待値: ValueError により reader contract drift を早期に検出できる。
@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: NormalizedSession(
                session_id="bad",
                source_format=cast(Any, "ruby"),
                source_state="complete",
                cwd=None,
                git_root=None,
                repository=None,
                branch=None,
                created_at=None,
                updated_at=None,
                selected_model=None,
                events=(),
                message_snapshots=(),
                issues=(),
                source_paths={},
            ),
            "source_format",
        ),
        (
            lambda: NormalizedSession(
                session_id="bad",
                source_format="current",
                source_state=cast(Any, "failed"),
                cwd=None,
                git_root=None,
                repository=None,
                branch=None,
                created_at=None,
                updated_at=None,
                selected_model=None,
                events=(),
                message_snapshots=(),
                issues=(),
                source_paths={},
            ),
            "source_state",
        ),
        (
            lambda: NormalizedEvent(
                sequence=1,
                kind=cast(Any, "api"),
                mapping_status="complete",
                raw_type=None,
                occurred_at=None,
                role=None,
                content=None,
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
            "kind",
        ),
        (
            lambda: NormalizedEvent(
                sequence=1,
                kind="unknown",
                mapping_status=cast(Any, "skipped"),
                raw_type=None,
                occurred_at=None,
                role=None,
                content=None,
                tool_calls=(),
                detail={},
                raw_payload={},
            ),
            "mapping_status",
        ),
        (
            lambda: ReadIssue(
                code="event.unknown_shape",
                message="unknown",
                severity=cast(Any, "info"),
                source_path=None,
                sequence=None,
            ),
            "severity",
        ),
    ],
)
def test_type_contract_rejects_unknown_enum_values(
    factory: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


# 概要・目的: root failure と session degraded issue が別 branch として扱われる契約を守る。
# テストケース: ReadFailureResult と ReadSuccessResult をそれぞれ生成する。
# 期待値: failure は sessions を持たず、success は root と sessions を持つ。
def test_read_result_separates_root_failure_from_session_success() -> None:
    failure = ReadFailureResult(
        code="root_missing",
        message="history root is missing",
        root_path="/missing/.copilot",
    )
    root = ResolvedHistoryRoot(
        requested_root="/tmp/.copilot",
        current_root="/tmp/.copilot/session-state",
        legacy_root="/tmp/.copilot/history-session-state",
    )
    success = ReadSuccessResult(root=root, sessions=())

    assert failure.code == "root_missing"
    assert not hasattr(failure, "sessions")
    assert success.root == root
    assert success.sessions == ()


# 概要・目的: projection dataclass が HTTP response や保存 schema ではない
# pure value として使える契約を守る。
# テストケース: conversation、activity、search text source を最小データで生成する。
# 期待値: projection は typed field のみを持ち、
# status_code や table_name のような境界外 field を持たない。
def test_projection_contracts_do_not_include_http_or_storage_fields() -> None:
    summary = ConversationSummary(message_count=1, preview="hello", empty_reason=None)
    conversation = ConversationProjection(
        entries=(
            ConversationEntry(
                sequence=1,
                role="user",
                content="hello",
                occurred_at=None,
                source_event_kind="message",
            ),
        ),
        summary=summary,
    )
    activity = ActivityProjection(
        entries=(
            ActivityEntry(
                sequence=2,
                category="unknown",
                body="raw event",
                occurred_at=None,
                source_event_kind="unknown",
            ),
        )
    )
    search = SearchTextSource(parts=("hello", "raw event"))

    assert conversation.summary.message_count == 1
    assert activity.entries[0].category == "unknown"
    assert search.parts == ("hello", "raw event")
    assert not hasattr(conversation, "status_code")
    assert not hasattr(search, "table_name")

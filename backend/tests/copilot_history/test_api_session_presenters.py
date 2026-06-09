from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.api.presenters import SessionDetailPresenter, SessionIndexPresenter
from copilot_history.types import MessageSnapshot, NormalizedEvent, NormalizedSession, ReadIssue

OCCURRED_AT = datetime(2026, 4, 28, 4, 0, 1, tzinfo=UTC)


def _event(*, sequence: int, content: str = "hello") -> NormalizedEvent:
    return NormalizedEvent(
        sequence=sequence,
        kind="message",
        mapping_status="complete",
        raw_type="user.message",
        occurred_at=OCCURRED_AT,
        role="user",
        content=content,
        tool_calls=(),
        detail={},
        raw_payload={"type": "user.message", "data": {"content": content}},
    )


def _session(
    *,
    session_id: str = "session-1",
    events: tuple[NormalizedEvent, ...] = (),
    issues: tuple[ReadIssue, ...] = (),
    message_snapshots: tuple[MessageSnapshot, ...] = (),
    source_state: str = "complete",
) -> NormalizedSession:
    return NormalizedSession(
        session_id=session_id,
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
        source_paths={"events": "/tmp/events.jsonl"},
    )


# 概要・目的: session 一覧 Presenter が projection 済み summary を success
# envelope に包む契約を守る。
# テストケース: 入力順の異なる 2 session のうち 1 件が degraded issue を持つ。
# 期待値: data は入力順の summary 配列になり、meta.count と
# meta.partial_results が返却件数と degraded 有無を表す。
def test_session_index_presenter_wraps_summaries_with_meta() -> None:
    issue = ReadIssue(
        code="workspace.unreadable",
        message="workspace metadata is not accessible",
        severity="warning",
        source_path="/tmp/workspace.yaml",
        sequence=None,
    )
    first = _session(session_id="first-session", events=(_event(sequence=1, content="first"),))
    second = _session(
        session_id="second-session",
        events=(_event(sequence=1, content="second"),),
        issues=(issue,),
        source_state="degraded",
    )

    body = SessionIndexPresenter().present((first, second))

    data = cast(list[dict[str, Any]], body["data"])
    assert [summary["id"] for summary in data] == ["first-session", "second-session"]
    assert body["meta"] == {"count": 2, "partial_results": True}


# 概要・目的: session 詳細 Presenter が detail projection を success envelope に
# 包み、raw opt-in をそのまま伝える契約を守る。
# テストケース: raw payload を持つ snapshot と event を include_raw false / true で
# それぞれ response body にする。
# 期待値: top-level は data のみで、raw_included と raw_payload 表現が
# include_raw の真偽に従って切り替わる。
def test_session_detail_presenter_wraps_detail_and_preserves_raw_switch() -> None:
    raw_payload: dict[str, object] = {
        "type": "user.message",
        "data": {"content": "hello"},
    }
    session = _session(
        events=(_event(sequence=1, content="hello"),),
        message_snapshots=(
            MessageSnapshot(
                sequence=1,
                role="user",
                content="hello",
                occurred_at=OCCURRED_AT,
                raw_payload=raw_payload,
            ),
        ),
    )
    presenter = SessionDetailPresenter()

    without_raw = presenter.present(session)
    with_raw = presenter.present(session, include_raw=True)
    without_data = cast(dict[str, Any], without_raw["data"])
    with_data = cast(dict[str, Any], with_raw["data"])
    without_snapshots = cast(list[dict[str, Any]], without_data["message_snapshots"])
    with_snapshots = cast(list[dict[str, Any]], with_data["message_snapshots"])

    assert set(without_raw) == {"data"}
    assert without_data["raw_included"] is False
    assert with_data["raw_included"] is True
    assert without_snapshots[0]["raw_payload"] is None
    assert with_snapshots[0]["raw_payload"] == raw_payload

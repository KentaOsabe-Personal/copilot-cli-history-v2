from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from copilot_history.api.presenters import (
    ErrorPresenter,
    HistorySyncPresenter,
    SessionDetailPresenter,
    SessionIndexPresenter,
)
from copilot_history.api.types import (
    HistorySyncCountsPresentationInput,
    HistorySyncPresentationResult,
    HistorySyncRunPresentationInput,
    ValidationErrorPresentationInput,
)
from copilot_history.types import (
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    NormalizedToolCall,
    ReadIssue,
)
from tests.copilot_history.api_contract_fixtures import (
    ApiContractFixtureRepository,
    JsonObject,
    assert_fixture_body_matches,
)

FIXTURES = ApiContractFixtureRepository.default()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _tool_call(
    *,
    name: str | None,
    arguments_preview: str | None,
    is_truncated: bool = False,
) -> NormalizedToolCall:
    return NormalizedToolCall(
        name=name,
        arguments_preview=arguments_preview,
        is_truncated=is_truncated,
    )


def _event(
    *,
    sequence: int,
    kind: str = "message",
    mapping_status: str = "complete",
    raw_type: str | None,
    occurred_at: str,
    role: str | None,
    content: str | None,
    tool_calls: tuple[NormalizedToolCall, ...] = (),
    detail: Mapping[str, object] | None = None,
    raw_payload: Mapping[str, object] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        sequence=sequence,
        kind=kind,  # type: ignore[arg-type]
        mapping_status=mapping_status,  # type: ignore[arg-type]
        raw_type=raw_type,
        occurred_at=_dt(occurred_at),
        role=role,
        content=content,
        tool_calls=tool_calls,
        detail={} if detail is None else detail,
        raw_payload={} if raw_payload is None else raw_payload,
    )


def _snapshot(
    *, role: str, content: str, raw_payload: Mapping[str, object] | None = None
) -> MessageSnapshot:
    return MessageSnapshot(
        sequence=1,
        role=role,
        content=content,
        occurred_at=None,
        raw_payload={} if raw_payload is None else raw_payload,
    )


def _session(
    *,
    session_id: str,
    source_format: str = "current",
    source_state: str = "complete",
    cwd: str | None,
    git_root: str | None,
    repository: str | None,
    branch: str | None,
    created_at: str,
    updated_at: str,
    selected_model: str | None,
    events: tuple[NormalizedEvent, ...],
    message_snapshots: tuple[MessageSnapshot, ...],
    issues: tuple[ReadIssue, ...] = (),
    source_paths: Mapping[str, str] | None = None,
) -> NormalizedSession:
    return NormalizedSession(
        session_id=session_id,
        source_format=source_format,  # type: ignore[arg-type]
        source_state=source_state,  # type: ignore[arg-type]
        cwd=cwd,
        git_root=git_root,
        repository=repository,
        branch=branch,
        created_at=_dt(created_at),
        updated_at=_dt(updated_at),
        selected_model=selected_model,
        events=events,
        message_snapshots=message_snapshots,
        issues=issues,
        source_paths={} if source_paths is None else source_paths,
    )


def _current_mixed_session() -> NormalizedSession:
    raw_user = {"type": "user.message", "data": {"content": "current mixed question"}}
    raw_assistant = {"type": "assistant.message", "data": {"content": "current mixed answer"}}
    return _session(
        session_id="current-schema-mixed",
        cwd="/workspace/current-schema-mixed",
        git_root="/workspace/current-schema-mixed",
        repository="octo/example",
        branch="feature/current-schema",
        created_at="2026-04-28T04:00:01Z",
        updated_at="2026-04-28T04:00:02Z",
        selected_model="gpt-5",
        events=(
            _event(
                sequence=1,
                raw_type="user.message",
                occurred_at="2026-04-28T04:00:01Z",
                role="user",
                content="current mixed question",
                raw_payload=raw_user,
            ),
            _event(
                sequence=2,
                raw_type="assistant.message",
                occurred_at="2026-04-28T04:00:02Z",
                role="assistant",
                content="current mixed answer",
                tool_calls=(
                    _tool_call(name="apply_patch", arguments_preview='{"cmd":"patch"}'),
                ),
                detail={"summary": "patched fixture files"},
                raw_payload=raw_assistant,
            ),
        ),
        message_snapshots=(
            _snapshot(role="user", content="current mixed question", raw_payload=raw_user),
            _snapshot(
                role="assistant",
                content="current mixed answer",
                raw_payload=raw_assistant,
            ),
        ),
        source_paths={"events": "/tmp/copilot/session-state/current-schema-mixed/events.jsonl"},
    )


def _current_mixed_list_session() -> NormalizedSession:
    return _session(
        session_id="current-schema-mixed",
        cwd="/workspace/current-schema-mixed",
        git_root="/workspace/current-schema-mixed",
        repository="octo/example",
        branch="feature/current-schema",
        created_at="2026-04-28T04:00:01Z",
        updated_at="2026-04-28T04:00:02Z",
        selected_model="gpt-5",
        events=(
            _event(
                sequence=1,
                raw_type="user.message",
                occurred_at="2026-04-28T04:00:01Z",
                role="user",
                content="current mixed question",
            ),
            _event(
                sequence=2,
                raw_type="assistant.message",
                occurred_at="2026-04-28T04:00:02Z",
                role="assistant",
                content="current mixed answer",
            ),
        ),
        message_snapshots=(
            _snapshot(role="user", content="current mixed question"),
            _snapshot(role="assistant", content="current mixed answer"),
        ),
    )


def _legacy_mixed_session() -> NormalizedSession:
    return _session(
        session_id="legacy-schema-mixed",
        source_format="legacy",
        cwd=None,
        git_root=None,
        repository=None,
        branch=None,
        created_at="2026-04-27T03:00:01Z",
        updated_at="2026-04-27T03:00:02Z",
        selected_model=None,
        events=(
            _event(
                sequence=1,
                raw_type="legacy.user_message",
                occurred_at="2026-04-27T03:00:01Z",
                role="user",
                content="legacy mixed question",
            ),
            _event(
                sequence=2,
                raw_type="legacy.assistant_message",
                occurred_at="2026-04-27T03:00:02Z",
                role="assistant",
                content="legacy mixed answer",
            ),
        ),
        message_snapshots=(
            _snapshot(role="user", content="legacy mixed question"),
            _snapshot(role="assistant", content="legacy mixed answer"),
        ),
    )


def _degraded_session() -> NormalizedSession:
    issue = ReadIssue(
        code="current.workspace_unreadable",
        severity="warning",
        message="workspace metadata is not accessible",
        source_path="/tmp/copilot/session-state/current-schema-degraded/workspace.yaml",
        sequence=None,
    )
    return _session(
        session_id="current-schema-degraded",
        source_state="degraded",
        cwd="/workspace/current-schema-degraded",
        git_root="/workspace/current-schema-degraded",
        repository="octo/example",
        branch="feature/current-schema",
        created_at="2026-04-28T04:00:01Z",
        updated_at="2026-04-28T04:00:02Z",
        selected_model="gpt-5",
        events=(
            _event(
                sequence=1,
                raw_type="user.message",
                occurred_at="2026-04-28T04:00:01Z",
                role="user",
                content="partially readable session",
            ),
            _event(
                sequence=2,
                raw_type="assistant.message",
                occurred_at="2026-04-28T04:00:02Z",
                role="assistant",
                content="partial answer",
            ),
            _event(
                sequence=3,
                kind="unknown",
                mapping_status="partial",
                raw_type="unknown.event",
                occurred_at="2026-04-28T04:00:02Z",
                role=None,
                content=None,
            ),
        ),
        message_snapshots=(
            _snapshot(role="user", content="partially readable session"),
            _snapshot(role="assistant", content="partial answer"),
        ),
        issues=(issue,),
    )


def _sync_run(
    *, run_id: int, status: str, started_at: str, finished_at: str | None
) -> HistorySyncRunPresentationInput:
    return HistorySyncRunPresentationInput(
        id=run_id,
        status=status,
        started_at=_dt(started_at),
        finished_at=None if finished_at is None else _dt(finished_at),
    )


def _sync_counts(
    *,
    processed_count: int,
    inserted_count: int,
    updated_count: int,
    saved_count: int,
    skipped_count: int,
    failed_count: int,
    degraded_count: int,
) -> HistorySyncCountsPresentationInput:
    return HistorySyncCountsPresentationInput(
        processed_count=processed_count,
        inserted_count=inserted_count,
        updated_count=updated_count,
        saved_count=saved_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        degraded_count=degraded_count,
    )


def _select_expected_shape(expected: object, actual: object) -> object:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {
            key: _select_expected_shape(expected_value, actual[key])
            for key, expected_value in expected.items()
        }
    if isinstance(expected, list) and isinstance(actual, list):
        return [
            _select_expected_shape(
                expected_item,
                _matching_actual_item(expected_item, actual, index),
            )
            for index, expected_item in enumerate(expected)
        ]
    return actual


def _matching_actual_item(expected_item: object, actual: list[object], index: int) -> object:
    if isinstance(expected_item, dict) and isinstance(expected_item.get("sequence"), int):
        expected_sequence = expected_item["sequence"]
        for actual_item in actual:
            if isinstance(actual_item, dict) and actual_item.get("sequence") == expected_sequence:
                return actual_item
    return actual[index]


# 概要・目的: session list Presenter が代表 fixture の一覧 response body と一致する契約を守る。
# テストケース: list_success、list_empty、list_degraded の Presenter 出力を fixture と比較する。
# 期待値: current / legacy 混在、empty list、degraded meta が
# scenario id 付き deep equality で一致する。
def test_session_list_presenter_matches_representative_fixtures() -> None:
    presenter = SessionIndexPresenter()

    assert_fixture_body_matches(
        FIXTURES,
        "sessions.index.list_success",
        presenter.present((_current_mixed_list_session(), _legacy_mixed_session())),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "sessions.index.list_empty",
        presenter.present(()),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "sessions.index.list_degraded",
        presenter.present((_degraded_session(),)),
    )


# 概要・目的: session detail Presenter が代表 fixture の詳細 response body と一致する契約を守る。
# テストケース: detail_success は full body、raw 切替 fixture は
# fixture が持つ raw 関連 shape に射影して比較する。
# 期待値: timeline、conversation、activity、raw_included、raw_payload の
# drift が fixture 差分として検出される。
def test_session_detail_presenter_matches_representative_fixtures() -> None:
    presenter = SessionDetailPresenter()

    assert_fixture_body_matches(
        FIXTURES,
        "sessions.show.detail_success",
        presenter.present(_current_mixed_session()),
    )

    without_raw = presenter.present(_current_mixed_session())
    without_expected = FIXTURES.expected_body("sessions.show.detail_without_raw")
    assert_fixture_body_matches(
        FIXTURES,
        "sessions.show.detail_without_raw",
        cast(JsonObject, _select_expected_shape(without_expected, without_raw)),
    )

    raw_only_session = _session(
        session_id="current-schema-mixed",
        cwd="/workspace/current-schema-mixed",
        git_root="/workspace/current-schema-mixed",
        repository="octo/example",
        branch="feature/current-schema",
        created_at="2026-04-28T04:00:01Z",
        updated_at="2026-04-28T04:00:02Z",
        selected_model="gpt-5",
        events=(
            _event(
                sequence=1,
                raw_type="user.message",
                occurred_at="2026-04-28T04:00:01Z",
                role="user",
                content="current mixed question",
                raw_payload={
                    "type": "user.message",
                    "data": {"content": "current mixed question"},
                },
            ),
        ),
        message_snapshots=(
            _snapshot(
                role="user",
                content="current mixed question",
                raw_payload={
                    "type": "user.message",
                    "data": {"content": "current mixed question"},
                },
            ),
        ),
        source_paths={"events": "/tmp/copilot/session-state/current-schema-mixed/events.jsonl"},
    )
    with_raw = presenter.present(raw_only_session, include_raw=True)
    with_raw_expected = FIXTURES.expected_body("sessions.show.detail_with_raw")
    assert_fixture_body_matches(
        FIXTURES,
        "sessions.show.detail_with_raw",
        cast(JsonObject, _select_expected_shape(with_raw_expected, with_raw)),
    )


# 概要・目的: history sync Presenter が代表 fixture の sync response body と一致する契約を守る。
# テストケース: succeeded、completed_with_issues、running conflict、root failure、
# persistence failure を比較する。
# 期待値: success/error envelope、sync_run、counts、failure details、meta が fixture と一致する。
def test_history_sync_presenter_matches_representative_fixtures() -> None:
    presenter = HistorySyncPresenter()
    ok_counts = _sync_counts(
        processed_count=2,
        inserted_count=2,
        updated_count=0,
        saved_count=2,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
    )
    failed_counts = _sync_counts(
        processed_count=0,
        inserted_count=0,
        updated_count=0,
        saved_count=0,
        skipped_count=0,
        failed_count=1,
        degraded_count=0,
    )

    assert_fixture_body_matches(
        FIXTURES,
        "history_sync.success",
        presenter.present(
            HistorySyncPresentationResult(
                kind="succeeded",
                sync_run=_sync_run(
                    run_id=101,
                    status="succeeded",
                    started_at="2026-04-30T08:55:00Z",
                    finished_at="2026-04-30T08:55:01Z",
                ),
                counts=ok_counts,
            )
        ),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "history_sync.completed_with_issues",
        presenter.present(
            HistorySyncPresentationResult(
                kind="completed_with_issues",
                sync_run=_sync_run(
                    run_id=102,
                    status="completed_with_issues",
                    started_at="2026-04-30T08:56:00Z",
                    finished_at="2026-04-30T08:56:02Z",
                ),
                counts=_sync_counts(
                    processed_count=2,
                    inserted_count=2,
                    updated_count=0,
                    saved_count=2,
                    skipped_count=0,
                    failed_count=0,
                    degraded_count=1,
                ),
            )
        ),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "history_sync.conflict",
        presenter.present(
            HistorySyncPresentationResult(
                kind="conflict",
                sync_run=_sync_run(
                    run_id=100,
                    status="running",
                    started_at="2026-04-30T08:55:00Z",
                    finished_at=None,
                ),
            )
        ),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "history_sync.root_failure",
        presenter.present(
            HistorySyncPresentationResult(
                kind="root_failure",
                sync_run=_sync_run(
                    run_id=103,
                    status="failed",
                    started_at="2026-04-30T08:57:00Z",
                    finished_at="2026-04-30T08:57:01Z",
                ),
                counts=failed_counts,
                error_code="root_missing",
                error_message="history root does not exist",
                error_details={"path": "/tmp/copilot-missing-home/.copilot"},
            )
        ),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "history_sync.persistence_failure",
        presenter.present(
            HistorySyncPresentationResult(
                kind="persistence_failure",
                sync_run=_sync_run(
                    run_id=104,
                    status="failed",
                    started_at="2026-04-30T08:58:00Z",
                    finished_at="2026-04-30T08:58:01Z",
                ),
                counts=failed_counts,
                error_code="history_sync_failed",
                error_message="history sync failed",
                error_details={
                    "failure_class": "ActiveRecord::RecordInvalid",
                    "sync_run_id": 104,
                },
            )
        ),
    )


# 概要・目的: common error Presenter が代表 fixture の error response body と一致する契約を守る。
# テストケース: session not found と session list validation error を fixture と比較する。
# 期待値: error.code、error.message、error.details の key と object 表現が一致する。
def test_common_error_presenter_matches_representative_fixtures() -> None:
    presenter = ErrorPresenter()

    assert_fixture_body_matches(
        FIXTURES,
        "sessions.show.not_found",
        presenter.from_not_found(session_id="missing-session"),
    )
    assert_fixture_body_matches(
        FIXTURES,
        "sessions.index.invalid_search_control_character",
        presenter.from_validation(
            ValidationErrorPresentationInput(
                code="invalid_session_list_query",
                message="session list query is invalid",
                details={
                    "field": "search",
                    "reason": "control_character",
                    "value": "hello\u0000world",
                },
            )
        ),
    )

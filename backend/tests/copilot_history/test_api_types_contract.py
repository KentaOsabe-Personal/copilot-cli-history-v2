from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from copilot_history.api.types import (
    ApiActivityEntryProjection,
    ApiConversationEntryProjection,
    ApiConversationSummaryProjection,
    ApiSessionDetailProjection,
    ApiTimelineEventProjection,
    ApiToolCallProjection,
    HistorySyncCountsPresentationInput,
    HistorySyncPresentationResult,
    HistorySyncRunPresentationInput,
    RootFailurePresentationInput,
    ValidationErrorPresentationInput,
)
from copilot_history.types import ReadIssue


# 概要・目的: API Presenter 専用 DTO が detail response に必要な
# projection field を HTTP や repository に依存せず保持できる契約を守る。
# テストケース: tool call、conversation、activity、timeline、detail projection を生成する。
# 期待値: fixture 互換に必要な status、raw_available、raw_payload、issue を
# 型付き field で参照できる。
def test_api_detail_projection_types_hold_presenter_only_fields() -> None:
    occurred_at = datetime(2026, 6, 9, 10, 0, tzinfo=UTC)
    issue = ReadIssue(
        code="event.partial",
        message="partial mapping",
        severity="warning",
        source_path="/tmp/events.jsonl",
        sequence=2,
    )
    tool_call = ApiToolCallProjection(
        name="functions.exec",
        arguments_preview='{"cmd":"pwd"}',
        is_truncated=False,
        status="partial",
    )
    conversation_entry = ApiConversationEntryProjection(
        sequence=2,
        role="assistant",
        content="実行します",
        occurred_at=occurred_at,
        tool_calls=(tool_call,),
        issues=(issue,),
    )
    activity_entry = ApiActivityEntryProjection(
        sequence=2,
        category="tool_call",
        title="functions.exec",
        summary='{"cmd":"pwd"}',
        raw_type="assistant.message",
        mapping_status="partial",
        occurred_at=occurred_at,
        source_path="/tmp/events.jsonl",
        raw_available=True,
        raw_payload={"type": "assistant.message"},
        issues=(issue,),
    )
    timeline_event = ApiTimelineEventProjection(
        sequence=2,
        kind="message",
        mapping_status="partial",
        raw_type="assistant.message",
        occurred_at=occurred_at,
        role="assistant",
        content="実行します",
        tool_calls=(tool_call,),
        detail=None,
        raw_payload={"type": "assistant.message"},
        issues=(issue,),
    )
    detail = ApiSessionDetailProjection(
        conversation_entries=(conversation_entry,),
        activity_entries=(activity_entry,),
        timeline_events=(timeline_event,),
        conversation_summary=ApiConversationSummaryProjection(
            has_conversation=True,
            message_count=1,
            preview="実行します",
            activity_count=1,
            empty_reason=None,
        ),
    )

    assert detail.conversation_entries[0].tool_calls[0].status == "partial"
    assert detail.activity_entries[0].raw_available is True
    assert detail.timeline_events[0].issues == (issue,)
    assert not hasattr(detail, "status_code")
    assert not hasattr(detail, "repository")


# 概要・目的: API projection DTO が immutable value として扱える境界を守る。
# テストケース: activity raw_payload の直接変更と frozen field 代入を試す。
# 期待値: frozen dataclass と read-only mapping により、どちらも変更できない。
def test_api_projection_types_are_immutable_and_freeze_payloads() -> None:
    activity_entry = ApiActivityEntryProjection(
        sequence=1,
        category="detail",
        title="tool result",
        summary=None,
        raw_type="tool.result",
        mapping_status="complete",
        occurred_at=None,
        source_path=None,
        raw_available=True,
        raw_payload={"type": "tool.result"},
        issues=(),
    )

    with pytest.raises(FrozenInstanceError):
        activity_entry.title = "changed"  # type: ignore[misc]

    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], activity_entry.raw_payload)["type"] = "changed"


# 概要・目的: sync counts DTO が負数を受け付けない契約を守る。
# テストケース: processed_count に負数を渡す。
# 期待値: ValueError により不正な sync result input を Presenter 前に検出できる。
def test_sync_counts_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="processed_count"):
        HistorySyncCountsPresentationInput(
            processed_count=-1,
            inserted_count=0,
            updated_count=0,
            saved_count=0,
            skipped_count=0,
            failed_count=0,
            degraded_count=0,
        )


# 概要・目的: sync result kind ごとの必須入力を fail fast で検出する契約を守る。
# テストケース: success、conflict、persistence failure と、不完全な root failure を生成する。
# 期待値: 正しい組み合わせは生成でき、不完全な failure は ValueError になる。
def test_sync_result_validates_required_fields_for_each_kind() -> None:
    started_at = datetime(2026, 6, 9, 10, 0, tzinfo=UTC)
    sync_run = HistorySyncRunPresentationInput(
        id=10,
        status="succeeded",
        started_at=started_at,
        finished_at=started_at,
    )
    counts = HistorySyncCountsPresentationInput(
        processed_count=3,
        inserted_count=1,
        updated_count=1,
        saved_count=2,
        skipped_count=1,
        failed_count=0,
        degraded_count=0,
    )

    success = HistorySyncPresentationResult(
        kind="succeeded",
        sync_run=sync_run,
        counts=counts,
    )
    conflict = HistorySyncPresentationResult(
        kind="conflict",
        sync_run=HistorySyncRunPresentationInput(
            id=11,
            status="running",
            started_at=started_at,
            finished_at=None,
        ),
    )
    persistence_failure = HistorySyncPresentationResult(
        kind="persistence_failure",
        sync_run=sync_run,
        counts=counts,
        error_code="history_sync_failed",
        error_message="failed to persist sessions",
        error_details={"reason": "database unavailable"},
    )

    assert success.counts == counts
    assert conflict.sync_run is not None
    assert persistence_failure.error_details["reason"] == "database unavailable"

    with pytest.raises(ValueError, match="error_code"):
        HistorySyncPresentationResult(
            kind="root_failure",
            sync_run=sync_run,
            error_message="history root is missing",
            error_details={"path": "/missing/.copilot"},
        )


# 概要・目的: common error DTO が upstream details key を改名せず保持する契約を守る。
# テストケース: validation error と root failure input を生成する。
# 期待値: details と path は read-only の Presenter 入力として参照できる。
def test_error_presentation_inputs_preserve_details_without_http_fields() -> None:
    validation = ValidationErrorPresentationInput(
        code="invalid_date_range",
        message="from must be before to",
        details={"from": "2026-06-10", "to": "2026-06-09"},
    )
    root_failure = RootFailurePresentationInput(
        code="root_missing",
        message="history root is missing",
        path="/missing/.copilot",
    )

    assert validation.details["from"] == "2026-06-10"
    assert root_failure.path == "/missing/.copilot"
    assert not hasattr(validation, "status_code")

    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], validation.details)["from"] = "changed"


# 概要・目的: enum 相当の API DTO field が仕様外の値を受け付けない契約を守る。
# テストケース: tool call status、timeline kind、sync result kind に不正値を渡す。
# 期待値: ValueError により Presenter contract drift を早期に検出できる。
@pytest.mark.parametrize(
    "factory",
    [
        lambda: ApiToolCallProjection(
            name=None,
            arguments_preview=None,
            is_truncated=False,
            status=cast(Any, "unknown"),
        ),
        lambda: ApiTimelineEventProjection(
            sequence=1,
            kind=cast(Any, "api"),
            mapping_status="complete",
            raw_type=None,
            occurred_at=None,
            role=None,
            content=None,
            tool_calls=(),
            detail=None,
            raw_payload={},
            issues=(),
        ),
        lambda: HistorySyncPresentationResult(kind=cast(Any, "queued")),
    ],
)
def test_api_types_reject_unknown_literal_values(factory: Any) -> None:
    with pytest.raises(ValueError):
        factory()

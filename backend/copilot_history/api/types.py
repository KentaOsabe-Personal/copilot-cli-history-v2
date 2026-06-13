from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from copilot_history.types import (
    EVENT_KIND_VALUES,
    MAPPING_STATUS_VALUES,
    ROOT_FAILURE_CODE_VALUES,
    EventKind,
    MappingStatus,
    ReadIssue,
    RootFailureCode,
    _validate_literal,
)

type ApiConversationRole = Literal["user", "assistant"]
type ApiToolCallStatus = MappingStatus
type ApiConversationEmptyReason = Literal[
    "no_events", "no_conversation_messages", "events_unavailable"
]
type HistorySyncPresentationKind = Literal[
    "succeeded",
    "completed_with_issues",
    "conflict",
    "root_failure",
    "persistence_failure",
]

API_CONVERSATION_ROLE_VALUES = ("user", "assistant")
API_CONVERSATION_EMPTY_REASON_VALUES = (
    "no_events",
    "no_conversation_messages",
    "events_unavailable",
)
HISTORY_SYNC_PRESENTATION_KIND_VALUES = (
    "succeeded",
    "completed_with_issues",
    "conflict",
    "root_failure",
    "persistence_failure",
)
SUCCESS_SYNC_RESULT_KINDS = ("succeeded", "completed_with_issues")


def _readonly_object_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


def _validate_sequence(value: int) -> None:
    if value < 1:
        msg = "sequence must be greater than or equal to 1"
        raise ValueError(msg)


def _validate_non_negative(field_name: str, value: int) -> None:
    if value < 0:
        msg = f"{field_name} must be non-negative"
        raise ValueError(msg)


@dataclass(frozen=True)
class SessionLookupPresentationInput:
    session_id: str

    def __post_init__(self) -> None:
        if not self.session_id:
            msg = "session_id must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True)
class ApiToolCallProjection:
    name: str | None
    arguments_preview: str | None
    is_truncated: bool
    status: ApiToolCallStatus

    def __post_init__(self) -> None:
        _validate_literal("status", self.status, MAPPING_STATUS_VALUES)


@dataclass(frozen=True)
class ApiConversationEntryProjection:
    sequence: int
    role: ApiConversationRole
    content: str
    occurred_at: datetime | None
    tool_calls: tuple[ApiToolCallProjection, ...]
    issues: tuple[ReadIssue, ...]

    def __post_init__(self) -> None:
        _validate_sequence(self.sequence)
        _validate_literal("role", self.role, API_CONVERSATION_ROLE_VALUES)
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True)
class ApiActivityEntryProjection:
    sequence: int
    category: str
    title: str
    summary: str | None
    raw_type: str | None
    mapping_status: MappingStatus
    occurred_at: datetime | None
    source_path: str | None
    raw_available: bool
    raw_payload: Mapping[str, object]
    issues: tuple[ReadIssue, ...]

    def __post_init__(self) -> None:
        _validate_sequence(self.sequence)
        _validate_literal("mapping_status", self.mapping_status, MAPPING_STATUS_VALUES)
        object.__setattr__(self, "raw_payload", _readonly_object_mapping(self.raw_payload))
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True)
class ApiConversationSummaryProjection:
    has_conversation: bool
    message_count: int
    preview: str | None
    activity_count: int
    empty_reason: ApiConversationEmptyReason | None

    def __post_init__(self) -> None:
        _validate_non_negative("message_count", self.message_count)
        _validate_non_negative("activity_count", self.activity_count)
        if self.empty_reason is not None:
            _validate_literal(
                "empty_reason", self.empty_reason, API_CONVERSATION_EMPTY_REASON_VALUES
            )


@dataclass(frozen=True)
class ApiTimelineEventProjection:
    sequence: int
    kind: EventKind
    mapping_status: MappingStatus
    raw_type: str | None
    occurred_at: datetime | None
    role: str | None
    content: str | None
    tool_calls: tuple[ApiToolCallProjection, ...]
    detail: Mapping[str, object] | None
    raw_payload: Mapping[str, object]
    issues: tuple[ReadIssue, ...]

    def __post_init__(self) -> None:
        _validate_sequence(self.sequence)
        _validate_literal("kind", self.kind, EVENT_KIND_VALUES)
        _validate_literal("mapping_status", self.mapping_status, MAPPING_STATUS_VALUES)
        detail = None if self.detail is None else _readonly_object_mapping(self.detail)
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "raw_payload", _readonly_object_mapping(self.raw_payload))
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True)
class ApiSessionDetailProjection:
    conversation_entries: tuple[ApiConversationEntryProjection, ...]
    activity_entries: tuple[ApiActivityEntryProjection, ...]
    timeline_events: tuple[ApiTimelineEventProjection, ...]
    conversation_summary: ApiConversationSummaryProjection

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_entries", tuple(self.conversation_entries))
        object.__setattr__(self, "activity_entries", tuple(self.activity_entries))
        object.__setattr__(self, "timeline_events", tuple(self.timeline_events))


@dataclass(frozen=True)
class HistorySyncRunPresentationInput:
    id: int | str
    status: str
    started_at: datetime | None
    finished_at: datetime | None

    def __post_init__(self) -> None:
        if isinstance(self.id, int) and self.id < 1:
            msg = "id must be greater than or equal to 1"
            raise ValueError(msg)
        if isinstance(self.id, str) and not self.id:
            msg = "id must not be empty"
            raise ValueError(msg)
        if not self.status:
            msg = "status must not be empty"
            raise ValueError(msg)


@dataclass(frozen=True)
class HistorySyncCountsPresentationInput:
    processed_count: int
    inserted_count: int
    updated_count: int
    saved_count: int
    skipped_count: int
    failed_count: int
    degraded_count: int

    def __post_init__(self) -> None:
        for field_name in (
            "processed_count",
            "inserted_count",
            "updated_count",
            "saved_count",
            "skipped_count",
            "failed_count",
            "degraded_count",
        ):
            _validate_non_negative(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class HistorySyncPresentationResult:
    kind: HistorySyncPresentationKind
    sync_run: HistorySyncRunPresentationInput | None = None
    counts: HistorySyncCountsPresentationInput | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_literal("kind", self.kind, HISTORY_SYNC_PRESENTATION_KIND_VALUES)
        object.__setattr__(self, "error_details", _readonly_object_mapping(self.error_details))
        if self.kind in SUCCESS_SYNC_RESULT_KINDS:
            self._validate_success()
        elif self.kind == "conflict":
            self._validate_conflict()
        elif self.kind == "root_failure":
            self._validate_error(require_counts=False)
        elif self.kind == "persistence_failure":
            self._validate_error(require_counts=True)

    def _validate_success(self) -> None:
        self._require_sync_run()
        self._require_counts()
        if self.error_code is not None or self.error_message is not None or self.error_details:
            msg = "success sync result must not include error fields"
            raise ValueError(msg)

    def _validate_conflict(self) -> None:
        self._require_sync_run()
        if self.sync_run is not None and self.sync_run.started_at is None:
            msg = "conflict sync result requires sync_run.started_at"
            raise ValueError(msg)
        if self.counts is not None:
            msg = "conflict sync result must not include counts"
            raise ValueError(msg)

    def _validate_error(self, *, require_counts: bool) -> None:
        self._require_sync_run()
        if require_counts:
            self._require_counts()
        if self.error_code is None:
            msg = "error_code is required for error sync result"
            raise ValueError(msg)
        if self.error_message is None:
            msg = "error_message is required for error sync result"
            raise ValueError(msg)

    def _require_sync_run(self) -> None:
        if self.sync_run is None:
            msg = "sync_run is required"
            raise ValueError(msg)

    def _require_counts(self) -> None:
        if self.counts is None:
            msg = "counts is required"
            raise ValueError(msg)


@dataclass(frozen=True)
class ValidationErrorPresentationInput:
    code: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code:
            msg = "code must not be empty"
            raise ValueError(msg)
        if not self.message:
            msg = "message must not be empty"
            raise ValueError(msg)
        object.__setattr__(self, "details", _readonly_object_mapping(self.details))


@dataclass(frozen=True)
class RootFailurePresentationInput:
    code: RootFailureCode
    message: str
    path: str

    def __post_init__(self) -> None:
        _validate_literal("code", self.code, ROOT_FAILURE_CODE_VALUES)
        if not self.message:
            msg = "message must not be empty"
            raise ValueError(msg)
        if not self.path:
            msg = "path must not be empty"
            raise ValueError(msg)

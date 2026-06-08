from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Literal

type SourceFormat = Literal["current", "legacy"]
type SourceState = Literal["complete", "workspace_only", "degraded"]
type EventKind = Literal["message", "detail", "unknown"]
type MappingStatus = Literal["complete", "partial"]
type IssueSeverity = Literal["warning", "error"]
type RootFailureCode = Literal["root_missing", "root_permission_denied", "root_unreadable"]

SOURCE_FORMAT_VALUES = ("current", "legacy")
SOURCE_STATE_VALUES = ("complete", "workspace_only", "degraded")
EVENT_KIND_VALUES = ("message", "detail", "unknown")
MAPPING_STATUS_VALUES = ("complete", "partial")
ISSUE_SEVERITY_VALUES = ("warning", "error")
ROOT_FAILURE_CODE_VALUES = ("root_missing", "root_permission_denied", "root_unreadable")


def _validate_literal(field_name: str, value: str, allowed_values: tuple[str, ...]) -> None:
    if value not in allowed_values:
        allowed = ", ".join(allowed_values)
        msg = f"{field_name} must be one of: {allowed}"
        raise ValueError(msg)


def _readonly_mapping(values: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(values))


def _readonly_object_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class NormalizedToolCall:
    name: str | None
    arguments_preview: str | None
    is_truncated: bool
    raw_payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", _readonly_object_mapping(self.raw_payload))


@dataclass(frozen=True)
class NormalizedEvent:
    sequence: int
    kind: EventKind
    mapping_status: MappingStatus
    raw_type: str | None
    occurred_at: datetime | None
    role: str | None
    content: str | None
    tool_calls: tuple[NormalizedToolCall, ...]
    detail: Mapping[str, object]
    raw_payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _validate_literal("kind", self.kind, EVENT_KIND_VALUES)
        _validate_literal("mapping_status", self.mapping_status, MAPPING_STATUS_VALUES)
        if self.sequence < 1:
            msg = "sequence must be greater than or equal to 1"
            raise ValueError(msg)
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(self, "detail", _readonly_object_mapping(self.detail))
        object.__setattr__(self, "raw_payload", _readonly_object_mapping(self.raw_payload))


@dataclass(frozen=True)
class MessageSnapshot:
    sequence: int
    role: str
    content: str
    occurred_at: datetime | None
    raw_payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            msg = "sequence must be greater than or equal to 1"
            raise ValueError(msg)
        object.__setattr__(self, "raw_payload", _readonly_object_mapping(self.raw_payload))


@dataclass(frozen=True)
class ReadIssue:
    code: str
    message: str
    severity: IssueSeverity
    source_path: str | None
    sequence: int | None

    def __post_init__(self) -> None:
        _validate_literal("severity", self.severity, ISSUE_SEVERITY_VALUES)
        if self.sequence is not None and self.sequence < 1:
            msg = "sequence must be greater than or equal to 1 when provided"
            raise ValueError(msg)


@dataclass(frozen=True)
class NormalizedSession:
    session_id: str
    source_format: SourceFormat
    source_state: SourceState
    cwd: str | None
    git_root: str | None
    repository: str | None
    branch: str | None
    created_at: datetime | None
    updated_at: datetime | None
    selected_model: str | None
    events: tuple[NormalizedEvent, ...]
    message_snapshots: tuple[MessageSnapshot, ...]
    issues: tuple[ReadIssue, ...]
    source_paths: Mapping[str, str]

    def __post_init__(self) -> None:
        _validate_literal("source_format", self.source_format, SOURCE_FORMAT_VALUES)
        _validate_literal("source_state", self.source_state, SOURCE_STATE_VALUES)
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "message_snapshots", tuple(self.message_snapshots))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "source_paths", _readonly_mapping(self.source_paths))

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def message_snapshot_count(self) -> int:
        return len(self.message_snapshots)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def degraded(self) -> bool:
        return self.source_state == "degraded"


@dataclass(frozen=True)
class ResolvedHistoryRoot:
    requested_root: str
    current_root: str
    legacy_root: str


@dataclass(frozen=True)
class ReadSuccessResult:
    root: ResolvedHistoryRoot
    sessions: tuple[NormalizedSession, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sessions", tuple(self.sessions))


@dataclass(frozen=True)
class ReadFailureResult:
    code: RootFailureCode
    message: str
    root_path: str

    def __post_init__(self) -> None:
        _validate_literal("code", self.code, ROOT_FAILURE_CODE_VALUES)


RootFailure = ReadFailureResult


@dataclass(frozen=True)
class SessionSource:
    session_id: str
    source_format: SourceFormat
    source_path: str
    artifact_paths: Mapping[str, str]
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id:
            msg = "session_id must not be empty"
            raise ValueError(msg)
        _validate_literal("source_format", self.source_format, SOURCE_FORMAT_VALUES)
        object.__setattr__(self, "artifact_paths", _readonly_mapping(self.artifact_paths))
        object.__setattr__(self, "metadata", _readonly_mapping(self.metadata))


@dataclass(frozen=True)
class ConversationEntry:
    sequence: int
    role: str
    content: str
    occurred_at: datetime | None
    source_event_kind: EventKind

    def __post_init__(self) -> None:
        _validate_literal("source_event_kind", self.source_event_kind, EVENT_KIND_VALUES)


@dataclass(frozen=True)
class ConversationSummary:
    message_count: int
    preview: str | None
    empty_reason: str | None

    def __post_init__(self) -> None:
        if self.message_count < 0:
            msg = "message_count must be non-negative"
            raise ValueError(msg)


@dataclass(frozen=True)
class ConversationProjection:
    entries: tuple[ConversationEntry, ...]
    summary: ConversationSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))


@dataclass(frozen=True)
class ActivityEntry:
    sequence: int
    category: str
    body: str | None
    occurred_at: datetime | None
    source_event_kind: EventKind

    def __post_init__(self) -> None:
        _validate_literal("source_event_kind", self.source_event_kind, EVENT_KIND_VALUES)


@dataclass(frozen=True)
class ActivityProjection:
    entries: tuple[ActivityEntry, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))


@dataclass(frozen=True)
class SearchTextSource:
    parts: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parts", tuple(self.parts))


@dataclass(frozen=True)
class NormalizationResult:
    event: NormalizedEvent
    issues: tuple[ReadIssue, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

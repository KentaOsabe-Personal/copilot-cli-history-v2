import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from copilot_history.types import (
    NormalizationResult,
    NormalizedEvent,
    NormalizedToolCall,
    ReadIssue,
    SourceFormat,
)

CURRENT_MESSAGE_TYPES = ("user.message", "assistant.message", "system.message")
LEGACY_MESSAGE_TYPES = ("user_message", "assistant_message", "system_message")
TOOL_ARGUMENT_PREVIEW_LIMIT = 240
REDACTED_ARGUMENT_KEYS = ("token", "secret", "password", "authorization", "cookie")
DETAIL_CATEGORIES = (
    (re.compile(r"\Aassistant\.turn_"), "assistant_turn"),
    (re.compile(r"\Atool\.execution_"), "tool_execution"),
    (re.compile(r"\Ahook\."), "hook"),
    (re.compile(r"\Askill\.invoked\Z"), "skill"),
)


class EventNormalizer:
    def normalize(
        self,
        raw_event: Mapping[str, object] | object,
        *,
        source_format: SourceFormat,
        sequence: int,
        source_path: str,
    ) -> NormalizationResult:
        if source_format not in ("current", "legacy"):
            msg = "source_format must be one of: current, legacy"
            raise ValueError(msg)

        payload = self._normalize_payload(raw_event)
        raw_type = self._extract_raw_type(payload, raw_event)

        if not isinstance(payload, Mapping):
            return self._unknown_result(
                payload={"value": payload},
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
            )

        if source_format == "legacy":
            return self._normalize_legacy_event(
                payload=payload,
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
            )
        return self._normalize_current_event(
            payload=payload,
            raw_type=raw_type,
            sequence=sequence,
            source_path=source_path,
        )

    def _normalize_current_event(
        self,
        *,
        payload: Mapping[str, object],
        raw_type: str,
        sequence: int,
        source_path: str,
    ) -> NormalizationResult:
        if raw_type in CURRENT_MESSAGE_TYPES:
            return self._normalize_current_message(
                payload=payload,
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
            )
        if raw_type in LEGACY_MESSAGE_TYPES:
            return self._normalize_legacy_event(
                payload=payload,
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
            )

        category = self._detail_category_for(raw_type)
        if category is not None:
            return self._normalize_current_detail(
                payload=payload,
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
                category=category,
            )

        return self._unknown_result(
            payload=payload,
            raw_type=raw_type,
            sequence=sequence,
            source_path=source_path,
        )

    def _normalize_legacy_event(
        self,
        *,
        payload: Mapping[str, object],
        raw_type: str,
        sequence: int,
        source_path: str,
    ) -> NormalizationResult:
        if raw_type not in LEGACY_MESSAGE_TYPES:
            return self._unknown_result(
                payload=payload,
                raw_type=raw_type,
                sequence=sequence,
                source_path=source_path,
            )

        role = self._presence(payload.get("role"))
        content = self._presence(payload.get("content"))
        occurred_at = self._parse_time(payload.get("timestamp"))
        is_partial = role is None or content is None or self._timestamp_missing_or_invalid(payload)
        return NormalizationResult(
            event=NormalizedEvent(
                sequence=sequence,
                kind="message",
                mapping_status="partial" if is_partial else "complete",
                raw_type=raw_type,
                occurred_at=occurred_at,
                role=role,
                content=content,
                tool_calls=(),
                detail={},
                raw_payload=payload,
            ),
            issues=(self._partial_mapping_issue(source_path=source_path, sequence=sequence),)
            if is_partial
            else (),
        )

    def _normalize_current_message(
        self,
        *,
        payload: Mapping[str, object],
        raw_type: str,
        sequence: int,
        source_path: str,
    ) -> NormalizationResult:
        data = payload.get("data")
        normalized_data = data if isinstance(data, Mapping) else {}
        role = self._presence(normalized_data.get("role")) or self._role_from_current_type(raw_type)
        content = self._presence(normalized_data.get("content"))
        occurred_at = self._parse_time(payload.get("timestamp"))
        tool_calls, tool_call_partial = self._extract_tool_calls(
            normalized_data.get("toolRequests")
        )
        is_partial = (
            role is None
            or self._missing_required_current_content(
                raw_type=raw_type, content=content, tool_calls=tool_calls
            )
            or self._timestamp_missing_or_invalid(payload)
            or tool_call_partial
        )
        return NormalizationResult(
            event=NormalizedEvent(
                sequence=sequence,
                kind="message",
                mapping_status="partial" if is_partial else "complete",
                raw_type=raw_type,
                occurred_at=occurred_at,
                role=role,
                content=content,
                tool_calls=tool_calls,
                detail={},
                raw_payload=payload,
            ),
            issues=(self._partial_mapping_issue(source_path=source_path, sequence=sequence),)
            if is_partial
            else (),
        )

    def _normalize_current_detail(
        self,
        *,
        payload: Mapping[str, object],
        raw_type: str,
        sequence: int,
        source_path: str,
        category: str,
    ) -> NormalizationResult:
        is_partial = self._timestamp_missing_or_invalid(payload)
        return NormalizationResult(
            event=NormalizedEvent(
                sequence=sequence,
                kind="detail",
                mapping_status="partial" if is_partial else "complete",
                raw_type=raw_type,
                occurred_at=self._parse_time(payload.get("timestamp")),
                role=None,
                content=None,
                tool_calls=(),
                detail={
                    "category": category,
                    "title": raw_type,
                    "body": self._detail_body_for(raw_type=raw_type, data=payload.get("data")),
                },
                raw_payload=payload,
            ),
            issues=(self._partial_mapping_issue(source_path=source_path, sequence=sequence),)
            if is_partial
            else (),
        )

    def _unknown_result(
        self,
        *,
        payload: Mapping[str, object],
        raw_type: str,
        sequence: int,
        source_path: str,
    ) -> NormalizationResult:
        return NormalizationResult(
            event=NormalizedEvent(
                sequence=sequence,
                kind="unknown",
                mapping_status="complete",
                raw_type=raw_type,
                occurred_at=self._parse_time(payload.get("timestamp")),
                role=None,
                content=None,
                tool_calls=(),
                detail={},
                raw_payload=payload,
            ),
            issues=(
                ReadIssue(
                    code="event.unknown_shape",
                    message="event payload could not be mapped to canonical fields",
                    severity="warning",
                    source_path=source_path,
                    sequence=sequence,
                ),
            ),
        )

    def _extract_tool_calls(
        self, raw_tool_requests: object
    ) -> tuple[tuple[NormalizedToolCall, ...], bool]:
        if raw_tool_requests is None:
            return (), False
        if not isinstance(raw_tool_requests, Sequence) or isinstance(
            raw_tool_requests, str | bytes | bytearray
        ):
            return (), True

        is_partial = False
        tool_calls: list[NormalizedToolCall] = []
        for raw_tool_request in raw_tool_requests:
            request_payload = self._normalize_payload(raw_tool_request)
            if not isinstance(request_payload, Mapping):
                is_partial = True
                tool_calls.append(
                    NormalizedToolCall(
                        name=None,
                        arguments_preview=None,
                        is_truncated=False,
                        raw_payload={"value": request_payload},
                    )
                )
                continue

            name = self._presence(request_payload.get("name"))
            arguments_preview, is_truncated, preview_missing = self._arguments_preview_for(
                request_payload.get("arguments")
            )
            if name is None or preview_missing:
                is_partial = True
            tool_calls.append(
                NormalizedToolCall(
                    name=name,
                    arguments_preview=arguments_preview,
                    is_truncated=is_truncated,
                    raw_payload=request_payload,
                )
            )

        return tuple(tool_calls), is_partial

    def _arguments_preview_for(self, arguments: object) -> tuple[str | None, bool, bool]:
        if arguments is None:
            return None, False, True

        try:
            preview = json.dumps(
                self._redact_sensitive_arguments(arguments),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except TypeError:
            preview = str(arguments)

        if not preview:
            return None, False, True
        if len(preview) <= TOOL_ARGUMENT_PREVIEW_LIMIT:
            return preview, False, False
        return preview[:TOOL_ARGUMENT_PREVIEW_LIMIT], True, False

    def _redact_sensitive_arguments(self, value: object, parent_key: str | None = None) -> object:
        if self._redact_key(parent_key):
            return "[REDACTED]"
        if isinstance(value, Mapping):
            return {
                str(key): self._redact_sensitive_arguments(child_value, str(key))
                for key, child_value in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return [
                self._redact_sensitive_arguments(child_value, parent_key) for child_value in value
            ]
        return value

    def _redact_key(self, key: str | None) -> bool:
        if key is None:
            return False
        lowered_key = key.lower()
        return any(candidate in lowered_key for candidate in REDACTED_ARGUMENT_KEYS)

    def _detail_category_for(self, raw_type: str) -> str | None:
        for pattern, category in DETAIL_CATEGORIES:
            if pattern.match(raw_type):
                return category
        return None

    def _detail_body_for(self, *, raw_type: str, data: object) -> str | None:
        normalized_data = data if isinstance(data, Mapping) else {}
        category = self._detail_category_for(raw_type)
        if category == "assistant_turn":
            return self._presence(normalized_data.get("turnId"))
        if category == "tool_execution":
            return self._join_present(
                normalized_data.get("toolName"), normalized_data.get("toolCallId")
            )
        if category == "hook":
            return self._join_present(
                normalized_data.get("hookEventName"), normalized_data.get("matcher")
            )
        if category == "skill":
            return self._join_present(
                normalized_data.get("skillName"), normalized_data.get("toolName")
            )
        return None

    def _join_present(self, *values: object) -> str:
        return " / ".join(value for value in (self._presence(item) for item in values) if value)

    def _role_from_current_type(self, raw_type: str) -> str | None:
        prefix = raw_type.split(".", 1)[0]
        return prefix if prefix in ("user", "assistant", "system") else None

    def _missing_required_current_content(
        self,
        *,
        raw_type: str,
        content: str | None,
        tool_calls: tuple[NormalizedToolCall, ...],
    ) -> bool:
        if raw_type in ("user.message", "assistant.message") and content is None and tool_calls:
            return False
        return content is None

    def _partial_mapping_issue(self, *, source_path: str, sequence: int) -> ReadIssue:
        return ReadIssue(
            code="event.partial_mapping",
            message="event payload matched partially",
            severity="warning",
            source_path=source_path,
            sequence=sequence,
        )

    def _normalize_payload(self, raw_event: object) -> object:
        if isinstance(raw_event, Mapping):
            return {str(key): self._normalize_payload(value) for key, value in raw_event.items()}
        if isinstance(raw_event, Sequence) and not isinstance(raw_event, str | bytes | bytearray):
            return [self._normalize_payload(value) for value in raw_event]
        return raw_event

    def _extract_raw_type(self, payload: object, raw_event: object) -> str:
        if isinstance(payload, Mapping):
            return str(payload.get("type", ""))
        return raw_event.__class__.__name__.lower()

    def _presence(self, value: object) -> str | None:
        if value is None:
            return None
        string_value = str(value)
        return string_value if string_value else None

    def _parse_time(self, value: object) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def _timestamp_missing_or_invalid(self, payload: Mapping[str, object]) -> bool:
        return "timestamp" not in payload or payload.get("timestamp") is None or self._parse_time(
            payload.get("timestamp")
        ) is None

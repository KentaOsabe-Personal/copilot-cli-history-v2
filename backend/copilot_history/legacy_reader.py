import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from copilot_history.event_normalizer import EventNormalizer
from copilot_history.types import (
    IssueSeverity,
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    ReadIssue,
    SessionSource,
)


class LegacySessionReader:
    def __init__(self, event_normalizer: EventNormalizer | None = None) -> None:
        self._event_normalizer = event_normalizer or EventNormalizer()

    def read(self, source: SessionSource) -> NormalizedSession:
        if source.source_format != "legacy":
            msg = "source format must be legacy"
            raise ValueError(msg)

        payload, source_issues = self._read_source(source)
        event_path = source.artifact_paths["legacy_json"]
        events, event_issues = self._normalize_events(payload, event_path)
        message_snapshots = self._normalize_message_snapshots(payload)
        issues = (*source_issues, *event_issues)
        return NormalizedSession(
            session_id=self._payload_text(payload, "sessionId") or source.session_id,
            source_format="legacy",
            source_state="degraded" if issues else "complete",
            cwd=None,
            git_root=None,
            repository=None,
            branch=None,
            created_at=self._parse_time(payload.get("startTime")),
            updated_at=self._latest_event_time(events),
            selected_model=self._payload_text(payload, "selectedModel"),
            events=events,
            message_snapshots=message_snapshots,
            issues=issues,
            source_paths=source.artifact_paths,
        )

    def _read_source(
        self, source: SessionSource
    ) -> tuple[Mapping[str, object], tuple[ReadIssue, ...]]:
        source_path = source.artifact_paths["legacy_json"]
        path = Path(source_path)
        if not self._readable_file(path):
            return {}, (
                self._issue(
                    code="legacy.source_unreadable",
                    message="legacy session source is not accessible",
                    severity="error",
                    source_path=source_path,
                ),
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return {}, (
                self._issue(
                    code="legacy.source_unreadable",
                    message="legacy session source is not accessible",
                    severity="error",
                    source_path=source_path,
                ),
            )
        except json.JSONDecodeError:
            return {}, (
                self._issue(
                    code="legacy.json_parse_failed",
                    message="legacy session JSON could not be parsed",
                    severity="error",
                    source_path=source_path,
                ),
            )
        if not isinstance(payload, Mapping):
            return {}, (
                self._issue(
                    code="legacy.json_parse_failed",
                    message="legacy session JSON could not be parsed",
                    severity="error",
                    source_path=source_path,
                ),
            )
        return {str(key): self._normalize_payload(value) for key, value in payload.items()}, ()

    def _normalize_events(
        self, payload: Mapping[str, object], source_path: str
    ) -> tuple[tuple[NormalizedEvent, ...], tuple[ReadIssue, ...]]:
        events: list[NormalizedEvent] = []
        issues: list[ReadIssue] = []
        for sequence, entry in enumerate(self._array_field(payload, "timeline"), start=1):
            result = self._event_normalizer.normalize(
                entry,
                source_format="legacy",
                sequence=sequence,
                source_path=source_path,
            )
            events.append(result.event)
            issues.extend(result.issues)
        return tuple(events), tuple(issues)

    def _normalize_message_snapshots(
        self, payload: Mapping[str, object]
    ) -> tuple[MessageSnapshot, ...]:
        snapshots: list[MessageSnapshot] = []
        for sequence, entry in enumerate(self._array_field(payload, "chatMessages"), start=1):
            normalized_entry = entry if isinstance(entry, Mapping) else {"value": entry}
            snapshots.append(
                MessageSnapshot(
                    sequence=sequence,
                    role=self._entry_text(normalized_entry, "role"),
                    content=self._entry_text(normalized_entry, "content"),
                    occurred_at=self._parse_time(normalized_entry.get("timestamp")),
                    raw_payload=normalized_entry,
                )
            )
        return tuple(snapshots)

    def _array_field(self, payload: Mapping[str, object], key: str) -> tuple[object, ...]:
        value = payload.get(key)
        if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
            return ()
        return tuple(value)

    def _normalize_payload(self, value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): self._normalize_payload(child_value)
                for key, child_value in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return [self._normalize_payload(child_value) for child_value in value]
        return value

    def _latest_event_time(self, events: tuple[NormalizedEvent, ...]) -> datetime | None:
        return max(
            (event.occurred_at for event in events if event.occurred_at is not None),
            default=None,
        )

    def _payload_text(self, payload: Mapping[str, object], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _entry_text(self, payload: Mapping[str, object], key: str) -> str:
        value = payload.get(key)
        if value is None:
            return ""
        return str(value)

    def _parse_time(self, value: object) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def _readable_file(self, path: Path) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False
        if not path.is_file():
            return False
        mode = stat.st_mode
        if hasattr(os, "geteuid") and stat.st_uid == os.geteuid():
            return bool(mode & 0o400)
        groups = {os.getegid(), *os.getgroups()} if hasattr(os, "getgroups") else {os.getegid()}
        if stat.st_gid in groups:
            return bool(mode & 0o040)
        return bool(mode & 0o004)

    def _issue(
        self,
        *,
        code: str,
        message: str,
        severity: IssueSeverity,
        source_path: str,
        sequence: int | None = None,
    ) -> ReadIssue:
        return ReadIssue(
            code=code,
            message=message,
            severity=severity,
            source_path=source_path,
            sequence=sequence,
        )

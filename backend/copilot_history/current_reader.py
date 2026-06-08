import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from copilot_history.event_normalizer import EventNormalizer
from copilot_history.types import (
    IssueSeverity,
    NormalizedEvent,
    NormalizedSession,
    ReadIssue,
    SessionSource,
    SourceState,
)


@dataclass(frozen=True)
class _EventReadResult:
    events: tuple[NormalizedEvent, ...]
    issues: tuple[ReadIssue, ...]
    events_mtime: datetime | None
    selected_model: str | None


@dataclass(frozen=True)
class _ModelCandidate:
    priority: int
    value: str


class CurrentSessionReader:
    def __init__(self, event_normalizer: EventNormalizer | None = None) -> None:
        self._event_normalizer = event_normalizer or EventNormalizer()

    def read(self, source: SessionSource) -> NormalizedSession:
        if source.source_format != "current":
            msg = "source format must be current"
            raise ValueError(msg)

        workspace_metadata, workspace_issues = self._read_workspace(
            source.artifact_paths["workspace"]
        )
        event_result = self._read_events(source)
        issues = (*workspace_issues, *event_result.issues)
        return NormalizedSession(
            session_id=self._metadata_text(workspace_metadata, "session_id") or source.session_id,
            source_format="current",
            source_state=self._source_state_for(
                workspace_issues=workspace_issues,
                event_issues=event_result.issues,
            ),
            cwd=self._metadata_text(workspace_metadata, "cwd"),
            git_root=self._metadata_text(workspace_metadata, "git_root"),
            repository=self._metadata_text(workspace_metadata, "repository"),
            branch=self._metadata_text(workspace_metadata, "branch"),
            created_at=self._parse_time(workspace_metadata.get("created_at")),
            updated_at=self._corrected_updated_at(
                events=event_result.events,
                events_mtime=event_result.events_mtime,
                workspace_metadata=workspace_metadata,
            ),
            selected_model=event_result.selected_model
            or self._metadata_text(workspace_metadata, "selected_model"),
            events=event_result.events,
            message_snapshots=(),
            issues=issues,
            source_paths=source.artifact_paths,
        )

    def _read_workspace(
        self, workspace_path: str
    ) -> tuple[Mapping[str, object], tuple[ReadIssue, ...]]:
        path = Path(workspace_path)
        if not self._readable_file(path):
            return {}, (
                self._issue(
                    code="current.workspace_unreadable",
                    message="workspace.yaml is not accessible",
                    severity="error",
                    source_path=workspace_path,
                ),
            )

        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError, UnicodeDecodeError):
            return {}, (
                self._issue(
                    code="current.workspace_parse_failed",
                    message="workspace.yaml could not be parsed",
                    severity="error",
                    source_path=workspace_path,
                ),
            )

        if not isinstance(payload, Mapping):
            return {}, (
                self._issue(
                    code="current.workspace_parse_failed",
                    message="workspace.yaml could not be parsed",
                    severity="error",
                    source_path=workspace_path,
                ),
            )
        return {str(key): value for key, value in payload.items()}, ()

    def _read_events(self, source: SessionSource) -> _EventReadResult:
        events_path = source.artifact_paths["events"]
        path = Path(events_path)
        if not path.exists():
            return _EventReadResult(
                events=(),
                issues=(
                    self._issue(
                        code="current.events_missing",
                        message="events.jsonl is missing for current session",
                        severity="warning",
                        source_path=events_path,
                    ),
                ),
                events_mtime=None,
                selected_model=None,
            )
        if not self._readable_file(path):
            return _EventReadResult(
                events=(),
                issues=(
                    self._issue(
                        code="current.events_unreadable",
                        message="events.jsonl is not accessible",
                        severity="error",
                        source_path=events_path,
                    ),
                ),
                events_mtime=None,
                selected_model=None,
            )

        events: list[NormalizedEvent] = []
        issues: list[ReadIssue] = []
        selected_model: _ModelCandidate | None = None
        try:
            events_mtime = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
            with path.open(encoding="utf-8") as event_file:
                for sequence, line in enumerate(event_file, start=1):
                    try:
                        raw_event = json.loads(line)
                    except json.JSONDecodeError:
                        issues.append(
                            self._issue(
                                code="current.event_parse_failed",
                                message="events.jsonl line could not be parsed",
                                severity="error",
                                source_path=events_path,
                                sequence=sequence,
                            )
                        )
                        continue

                    selected_model = self._choose_model_candidate(
                        selected_model,
                        self._extract_model_candidate(raw_event),
                    )
                    result = self._event_normalizer.normalize(
                        raw_event,
                        source_format="current",
                        sequence=sequence,
                        source_path=events_path,
                    )
                    events.append(result.event)
                    issues.extend(result.issues)
        except OSError:
            return _EventReadResult(
                events=(),
                issues=(
                    self._issue(
                        code="current.events_unreadable",
                        message="events.jsonl is not accessible",
                        severity="error",
                        source_path=events_path,
                    ),
                ),
                events_mtime=None,
                selected_model=None,
            )

        return _EventReadResult(
            events=tuple(events),
            issues=tuple(issues),
            events_mtime=events_mtime,
            selected_model=selected_model.value if selected_model is not None else None,
        )

    def _source_state_for(
        self, *, workspace_issues: tuple[ReadIssue, ...], event_issues: tuple[ReadIssue, ...]
    ) -> SourceState:
        if workspace_issues:
            return "degraded"
        if (
            len(event_issues) == 1
            and event_issues[0].code == "current.events_missing"
            and event_issues[0].severity == "warning"
        ):
            return "workspace_only"
        return "degraded" if event_issues else "complete"

    def _corrected_updated_at(
        self,
        *,
        events: tuple[NormalizedEvent, ...],
        events_mtime: datetime | None,
        workspace_metadata: Mapping[str, object],
    ) -> datetime | None:
        event_updated_at = max(
            (event.occurred_at for event in events if event.occurred_at is not None),
            default=None,
        )
        return (
            event_updated_at
            or events_mtime
            or self._parse_time(workspace_metadata.get("updated_at"))
            or self._parse_time(workspace_metadata.get("created_at"))
        )

    def _extract_model_candidate(self, raw_event: object) -> _ModelCandidate | None:
        if not isinstance(raw_event, Mapping):
            return None

        raw_type = raw_event.get("type")
        data = raw_event.get("data") if isinstance(raw_event.get("data"), Mapping) else {}
        data_mapping = data if isinstance(data, Mapping) else {}
        candidates: list[_ModelCandidate] = []
        if raw_type == "session.shutdown":
            self._append_model_candidate(candidates, 3, data_mapping.get("currentModel"))
        if raw_type == "tool.execution_complete":
            self._append_model_candidate(candidates, 2, data_mapping.get("model"))
        if raw_type == "assistant.usage":
            self._append_model_candidate(candidates, 1, data_mapping.get("model"))
        self._append_model_candidate(candidates, 0, raw_event.get("model"))
        selected: _ModelCandidate | None = None
        for candidate in candidates:
            selected = self._choose_model_candidate(selected, candidate)
        return selected

    def _append_model_candidate(
        self, candidates: list[_ModelCandidate], priority: int, value: object
    ) -> None:
        if not isinstance(value, str):
            return
        normalized = value.strip()
        if normalized:
            candidates.append(_ModelCandidate(priority=priority, value=normalized))

    def _choose_model_candidate(
        self, current: _ModelCandidate | None, next_candidate: _ModelCandidate | None
    ) -> _ModelCandidate | None:
        if next_candidate is None:
            return current
        if current is None or next_candidate.priority >= current.priority:
            return next_candidate
        return current

    def _metadata_text(self, metadata: Mapping[str, object], key: str) -> str | None:
        value = metadata.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _parse_time(self, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
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

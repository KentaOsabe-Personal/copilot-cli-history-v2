from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from copilot_history.api.response_projection import SessionResponseProjector
from copilot_history.types import NormalizedSession
from history_read_model.fake_repository import CopilotSessionRow

SEARCH_TEXT_VERSION = 2

type SessionRowBuildStatus = Literal["persistable", "workspace_only", "invalid"]


@dataclass(frozen=True)
class SessionRowBuildCandidate:
    session_id: str
    status: SessionRowBuildStatus
    row: CopilotSessionRow | None = None
    error_reasons: tuple[str, ...] = ()


def build_copilot_session_write_input(
    session: NormalizedSession,
    *,
    source_fingerprint: Mapping[str, object],
    indexed_at: datetime,
    projector: SessionResponseProjector | None = None,
) -> SessionRowBuildCandidate:
    if session.source_state == "workspace_only":
        return SessionRowBuildCandidate(session_id=session.session_id, status="workspace_only")

    display_time = session.updated_at or session.created_at
    if display_time is None:
        return SessionRowBuildCandidate(
            session_id=session.session_id,
            status="invalid",
            error_reasons=("created_at or updated_at is required",),
        )

    response_projector = projector or SessionResponseProjector()
    summary_payload = response_projector.project_summary(session)
    detail_payload = response_projector.project_detail(session, include_raw=False)
    conversation_summary = _mapping_value(summary_payload.get("conversation_summary"))

    row = CopilotSessionRow(
        session_id=session.session_id,
        source_format=session.source_format,
        source_state=session.source_state,
        created_at_source=session.created_at,
        updated_at_source=session.updated_at,
        source_partition_date=display_time.date(),
        cwd=session.cwd,
        git_root=session.git_root,
        repository=session.repository,
        branch=session.branch,
        selected_model=session.selected_model,
        event_count=session.event_count,
        message_snapshot_count=session.message_snapshot_count,
        issue_count=session.issue_count,
        message_count=_int_value(conversation_summary.get("message_count")),
        activity_count=_int_value(conversation_summary.get("activity_count")),
        degraded=session.degraded or bool(session.issues),
        conversation_preview=_str_or_none(conversation_summary.get("preview")),
        source_paths=_stringified_source_paths(session.source_paths),
        source_fingerprint=source_fingerprint,
        summary_payload=summary_payload,
        detail_payload=detail_payload,
        search_text=_build_search_text(
            summary_payload=summary_payload,
            detail_payload=detail_payload,
        ),
        search_text_version=SEARCH_TEXT_VERSION,
        indexed_at=indexed_at,
    )
    return SessionRowBuildCandidate(session_id=session.session_id, status="persistable", row=row)


def _build_search_text(
    *,
    summary_payload: Mapping[str, object],
    detail_payload: Mapping[str, object],
) -> str:
    values: list[object | None] = []
    summary = _mapping_value(summary_payload.get("conversation_summary"))
    values.append(summary.get("preview"))

    issues = _list_value(detail_payload.get("issues"))
    values.extend(_issue_values(issues))

    conversation = _mapping_value(detail_payload.get("conversation"))
    conversation_summary = _mapping_value(conversation.get("summary"))
    values.append(conversation_summary.get("preview"))
    for entry in _list_value(conversation.get("entries")):
        entry_mapping = _mapping_value(entry)
        values.append(entry_mapping.get("content"))
        values.extend(_issue_values(_list_value(entry_mapping.get("issues"))))

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalize_search_value(value)
        if text is None or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return "\n".join(normalized)


def _issue_values(issues: list[object]) -> list[object | None]:
    values: list[object | None] = []
    for issue in issues:
        issue_mapping = _mapping_value(issue)
        values.append(issue_mapping.get("code"))
        values.append(issue_mapping.get("message"))
    return values


def _normalize_search_value(value: object | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _mapping_value(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _int_value(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _stringified_source_paths(source_paths: Mapping[str, str]) -> Mapping[str, object]:
    return {str(role): str(path) for role, path in sorted(source_paths.items())}


__all__ = [
    "SEARCH_TEXT_VERSION",
    "SessionRowBuildCandidate",
    "SessionRowBuildStatus",
    "build_copilot_session_write_input",
]

from collections.abc import Mapping
from datetime import UTC, datetime

from copilot_history.api.presenters.issue_presenter import IssuePresenter
from copilot_history.types import (
    MessageSnapshot,
    NormalizedEvent,
    NormalizedSession,
    NormalizedToolCall,
    ReadIssue,
)

PREVIEW_LIMIT = 160


class SessionResponseProjector:
    def __init__(self, issue_presenter: IssuePresenter | None = None) -> None:
        self._issue_presenter = issue_presenter or IssuePresenter()

    def project_summary(self, session: NormalizedSession) -> dict[str, object]:
        conversation_summary = self._conversation_summary(session)
        return {
            "id": session.session_id,
            "source_format": session.source_format,
            "created_at": self._format_datetime(session.created_at),
            "updated_at": self._format_datetime(session.updated_at),
            "work_context": self._work_context(session),
            "selected_model": session.selected_model,
            "source_state": session.source_state,
            "event_count": session.event_count,
            "message_snapshot_count": session.message_snapshot_count,
            "conversation_summary": {
                "has_conversation": conversation_summary["has_conversation"],
                "message_count": conversation_summary["message_count"],
                "preview": conversation_summary["preview"],
                "activity_count": conversation_summary["activity_count"],
            },
            "degraded": self._session_degraded(session),
            "issues": self._issue_presenter.present_many(self._session_issues(session)),
        }

    def project_detail(
        self, session: NormalizedSession, *, include_raw: bool
    ) -> dict[str, object]:
        event_issues = self._event_issues_by_sequence(session)
        conversation_entries = self._conversation_entries(
            session.events, event_issues=event_issues
        )
        activity_entries = self._activity_entries(
            session, include_raw=include_raw, event_issues=event_issues
        )
        conversation_summary = self._conversation_summary(session)
        detail_summary = dict(conversation_summary)
        detail_summary["activity_count"] = len(activity_entries)
        return {
            "id": session.session_id,
            "source_format": session.source_format,
            "created_at": self._format_datetime(session.created_at),
            "updated_at": self._format_datetime(session.updated_at),
            "work_context": self._work_context(session),
            "selected_model": session.selected_model,
            "source_state": session.source_state,
            "degraded": self._session_degraded(session),
            "raw_included": include_raw,
            "issues": self._issue_presenter.present_many(self._session_issues(session)),
            "message_snapshots": [
                self._message_snapshot(snapshot, include_raw=include_raw)
                for snapshot in session.message_snapshots
            ],
            "conversation": {
                "entries": conversation_entries,
                "message_count": conversation_summary["message_count"],
                "empty_reason": conversation_summary["empty_reason"],
                "summary": {
                    "has_conversation": conversation_summary["has_conversation"],
                    "message_count": conversation_summary["message_count"],
                    "preview": conversation_summary["preview"],
                    "activity_count": detail_summary["activity_count"],
                },
            },
            "activity": {"entries": activity_entries},
            "timeline": [
                self._timeline_event(
                    event,
                    include_raw=include_raw,
                    issues=event_issues.get(event.sequence, ()),
                )
                for event in session.events
            ],
        }

    def _conversation_entries(
        self,
        events: tuple[NormalizedEvent, ...],
        *,
        event_issues: Mapping[int, tuple[ReadIssue, ...]],
    ) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for event in events:
            if not self._is_conversation_event(event):
                continue
            issues = event_issues.get(event.sequence, ())
            entries.append(
                {
                    "sequence": event.sequence,
                    "role": event.role,
                    "content": self._present_text(event.content),
                    "occurred_at": self._format_datetime(event.occurred_at),
                    "tool_calls": [
                        self._tool_call(tool_call, event) for tool_call in event.tool_calls
                    ],
                    "degraded": bool(issues),
                    "issues": self._issue_presenter.present_many(issues),
                }
            )
        return entries

    def _activity_entries(
        self,
        session: NormalizedSession,
        *,
        include_raw: bool,
        event_issues: Mapping[int, tuple[ReadIssue, ...]],
    ) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for event in session.events:
            if self._is_plain_conversation_event(event) and not include_raw:
                continue
            issues = event_issues.get(event.sequence, ())
            entries.append(
                {
                    "sequence": event.sequence,
                    "category": self._activity_category(event),
                    "title": self._activity_title(event),
                    "summary": self._activity_summary(event),
                    "raw_type": event.raw_type,
                    "mapping_status": event.mapping_status,
                    "occurred_at": self._format_datetime(event.occurred_at),
                    "source_path": self._event_source_path(session, issues=issues),
                    "raw_available": bool(event.raw_payload),
                    "raw_payload": self._raw_payload(event.raw_payload, include_raw=include_raw),
                    "degraded": bool(issues),
                    "issues": self._issue_presenter.present_many(issues),
                }
            )
        return entries

    def _timeline_event(
        self,
        event: NormalizedEvent,
        *,
        include_raw: bool,
        issues: tuple[ReadIssue, ...],
    ) -> dict[str, object]:
        return {
            "sequence": event.sequence,
            "kind": event.kind,
            "mapping_status": event.mapping_status,
            "raw_type": event.raw_type,
            "occurred_at": self._format_datetime(event.occurred_at),
            "role": event.role,
            "content": self._present_text(event.content),
            "tool_calls": [self._tool_call(tool_call, event) for tool_call in event.tool_calls],
            "detail": self._timeline_detail(event),
            "raw_payload": self._raw_payload(event.raw_payload, include_raw=include_raw),
            "degraded": bool(issues),
            "issues": self._issue_presenter.present_many(issues),
        }

    def _message_snapshot(
        self, snapshot: MessageSnapshot, *, include_raw: bool
    ) -> dict[str, object]:
        return {
            "role": snapshot.role,
            "content": snapshot.content,
            "raw_payload": self._raw_payload(snapshot.raw_payload, include_raw=include_raw),
        }

    def _conversation_summary(self, session: NormalizedSession) -> dict[str, object]:
        entries = [
            event
            for event in session.events
            if self._is_conversation_event(event)
        ]
        preview = self._preview_for(entries)
        return {
            "has_conversation": bool(entries),
            "message_count": len(entries),
            "preview": preview,
            "activity_count": sum(
                1 for event in session.events if not self._is_plain_conversation_event(event)
            ),
            "empty_reason": None if entries else self._empty_reason_for(session),
        }

    def _preview_for(self, events: list[NormalizedEvent]) -> str | None:
        if not events:
            return None
        content = self._present_text(events[0].content)
        if content is None:
            return None
        return content if len(content) <= PREVIEW_LIMIT else content[:PREVIEW_LIMIT]

    def _tool_call(
        self, tool_call: NormalizedToolCall, event: NormalizedEvent
    ) -> dict[str, object]:
        return {
            "name": tool_call.name,
            "arguments_preview": tool_call.arguments_preview,
            "is_truncated": tool_call.is_truncated,
            "status": event.mapping_status,
        }

    def _activity_category(self, event: NormalizedEvent) -> str:
        category = event.detail.get("category")
        if isinstance(category, str) and category:
            return category
        if event.tool_calls:
            return "tool_call"
        if event.kind == "message":
            return "message"
        if event.kind == "detail":
            return "detail"
        return "unknown"

    def _activity_title(self, event: NormalizedEvent) -> str:
        title = event.detail.get("title")
        if isinstance(title, str) and title:
            return title
        if event.tool_calls:
            return event.tool_calls[0].name or "unknown_tool"
        if event.kind == "message":
            return f"{event.role or 'message'} message"
        return event.raw_type or "unknown event"

    def _activity_summary(self, event: NormalizedEvent) -> str | None:
        summary = event.detail.get("summary")
        if isinstance(summary, str) and summary:
            return summary
        body = event.detail.get("body")
        if isinstance(body, str) and body:
            return body
        if event.tool_calls:
            return self._tool_call_summary(event)
        if content := self._present_text(event.content):
            return content
        if event.raw_type is not None:
            return event.raw_type
        return None

    def _timeline_detail(self, event: NormalizedEvent) -> dict[str, object] | None:
        if event.kind == "message" or not event.detail:
            return None
        return dict(event.detail)

    def _tool_call_summary(self, event: NormalizedEvent) -> str | None:
        summaries = [
            preview
            for tool_call in event.tool_calls
            if (preview := tool_call.arguments_preview) is not None
        ]
        return "; ".join(summaries) if summaries else None

    def _event_issues_by_sequence(
        self, session: NormalizedSession
    ) -> dict[int, tuple[ReadIssue, ...]]:
        grouped: dict[int, list[ReadIssue]] = {}
        for issue in session.issues:
            if issue.sequence is None:
                continue
            grouped.setdefault(issue.sequence, []).append(issue)
        return {sequence: tuple(issues) for sequence, issues in grouped.items()}

    def _session_issues(self, session: NormalizedSession) -> tuple[ReadIssue, ...]:
        return tuple(issue for issue in session.issues if issue.sequence is None)

    def _session_degraded(self, session: NormalizedSession) -> bool:
        return session.source_state == "degraded" or bool(session.issues)

    def _work_context(self, session: NormalizedSession) -> dict[str, object]:
        return {
            "cwd": session.cwd,
            "git_root": session.git_root,
            "repository": session.repository,
            "branch": session.branch,
        }

    def _event_source_path(
        self, session: NormalizedSession, *, issues: tuple[ReadIssue, ...]
    ) -> str | None:
        if events_path := session.source_paths.get("events"):
            return events_path
        if session_path := session.source_paths.get("session"):
            return session_path
        if issues:
            return issues[0].source_path
        return next(iter(session.source_paths.values()), None)

    def _raw_payload(self, payload: Mapping[str, object], *, include_raw: bool) -> object:
        if not include_raw or not payload:
            return None
        return dict(payload)

    def _is_conversation_event(self, event: NormalizedEvent) -> bool:
        return (
            event.kind == "message"
            and event.role in ("user", "assistant")
            and self._present_text(event.content) is not None
        )

    def _is_plain_conversation_event(self, event: NormalizedEvent) -> bool:
        return self._is_conversation_event(event) and not event.tool_calls

    def _empty_reason_for(self, session: NormalizedSession) -> str:
        return "no_events" if not session.events else "no_conversation_messages"

    def _present_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text if text else None

    def _format_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        utc_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return utc_value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = ["SessionResponseProjector"]

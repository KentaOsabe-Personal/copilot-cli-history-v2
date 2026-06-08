from copilot_history.types import (
    ActivityEntry,
    ActivityProjection,
    ConversationEntry,
    ConversationProjection,
    ConversationSummary,
    NormalizedEvent,
    NormalizedSession,
    SearchTextSource,
)

PREVIEW_LIMIT = 160


class ConversationProjector:
    def project(self, session: NormalizedSession) -> ConversationProjection:
        entries = tuple(
            ConversationEntry(
                sequence=event.sequence,
                role=event.role,
                content=content,
                occurred_at=event.occurred_at,
                source_event_kind=event.kind,
            )
            for event in session.events
            if self._is_conversation_event(event)
            if (content := self._present_text(event.content)) is not None
            if event.role is not None
        )
        return ConversationProjection(
            entries=entries,
            summary=ConversationSummary(
                message_count=len(entries),
                preview=self._preview_for(entries),
                empty_reason=None if entries else self._empty_reason_for(session),
            ),
        )

    def _is_conversation_event(self, event: NormalizedEvent) -> bool:
        return event.kind == "message" and event.role in ("user", "assistant")

    def _preview_for(self, entries: tuple[ConversationEntry, ...]) -> str | None:
        if not entries:
            return None
        return self._truncate(entries[0].content)

    def _empty_reason_for(self, session: NormalizedSession) -> str:
        return "no_events" if not session.events else "no_conversation_messages"

    def _present_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text if text else None

    def _truncate(self, value: str) -> str:
        if len(value) <= PREVIEW_LIMIT:
            return value
        return value[:PREVIEW_LIMIT]


class ActivityProjector:
    def project(self, session: NormalizedSession) -> ActivityProjection:
        entries: list[ActivityEntry] = []
        for event in session.events:
            if self._is_plain_conversation_event(event):
                continue
            entries.append(
                ActivityEntry(
                    sequence=event.sequence,
                    category=self._category_for(event),
                    body=self._body_for(event),
                    occurred_at=event.occurred_at,
                    source_event_kind=event.kind,
                )
            )
        return ActivityProjection(entries=tuple(entries))

    def _is_plain_conversation_event(self, event: NormalizedEvent) -> bool:
        return (
            event.kind == "message"
            and event.role in ("user", "assistant")
            and self._present_text(event.content) is not None
            and not event.tool_calls
        )

    def _category_for(self, event: NormalizedEvent) -> str:
        if event.tool_calls:
            return "tool_call"
        if event.kind == "message":
            return event.role or "message"
        if event.kind == "detail":
            category = event.detail.get("category")
            return category if isinstance(category, str) and category else "detail"
        return "unknown"

    def _body_for(self, event: NormalizedEvent) -> str | None:
        if event.tool_calls:
            return self._tool_call_body_for(event)
        if event.kind == "message":
            return self._present_text(event.content)
        if event.kind == "detail":
            body = event.detail.get("body")
            if isinstance(body, str) and body:
                return body
            title = event.detail.get("title")
            return title if isinstance(title, str) and title else event.raw_type
        return event.raw_type

    def _tool_call_body_for(self, event: NormalizedEvent) -> str | None:
        parts: list[str] = []
        for tool_call in event.tool_calls:
            name = tool_call.name or "unknown_tool"
            preview = tool_call.arguments_preview
            parts.append(f"{name} {preview}" if preview else name)
        return "; ".join(parts) if parts else None

    def _present_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text if text else None


class SearchTextProjector:
    def __init__(self, conversation_projector: ConversationProjector | None = None) -> None:
        self._conversation_projector = conversation_projector or ConversationProjector()

    def project(self, session: NormalizedSession) -> SearchTextSource:
        conversation = self._conversation_projector.project(session)
        parts: list[str] = []
        for entry in conversation.entries:
            self._append_unique(parts, entry.content)
        if conversation.summary.preview is not None:
            self._append_unique(parts, conversation.summary.preview)
        for issue in session.issues:
            self._append_unique(parts, issue.message)
        return SearchTextSource(parts=tuple(parts))

    def _append_unique(self, parts: list[str], value: str) -> None:
        text = value.strip()
        if text and text not in parts:
            parts.append(text)


__all__ = ["ActivityProjector", "ConversationProjector", "SearchTextProjector"]

"""Presenter helpers for Copilot history API response bodies."""

from typing import Any

__all__ = [
    "ErrorPresenter",
    "HistorySyncPresenter",
    "IssuePresenter",
    "SessionDetailPresenter",
    "SessionIndexPresenter",
]


def __getattr__(name: str) -> Any:
    if name == "ErrorPresenter":
        from copilot_history.api.presenters.error_presenter import ErrorPresenter

        return ErrorPresenter
    if name == "HistorySyncPresenter":
        from copilot_history.api.presenters.history_sync_presenter import HistorySyncPresenter

        return HistorySyncPresenter
    if name == "IssuePresenter":
        from copilot_history.api.presenters.issue_presenter import IssuePresenter

        return IssuePresenter
    if name == "SessionDetailPresenter":
        from copilot_history.api.presenters.session_detail_presenter import SessionDetailPresenter

        return SessionDetailPresenter
    if name == "SessionIndexPresenter":
        from copilot_history.api.presenters.session_index_presenter import SessionIndexPresenter

        return SessionIndexPresenter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from datetime import UTC, datetime

from copilot_history.api.types import (
    HistorySyncCountsPresentationInput,
    HistorySyncPresentationResult,
    HistorySyncRunPresentationInput,
)

HISTORY_SYNC_RUNNING_CODE = "history_sync_running"
HISTORY_SYNC_RUNNING_MESSAGE = "history sync is already running"


class HistorySyncPresenter:
    def present(self, result: HistorySyncPresentationResult) -> dict[str, object]:
        if result.kind in ("succeeded", "completed_with_issues"):
            return {"data": self._success_data(result)}
        if result.kind == "conflict":
            return {"error": self._conflict_error(result)}
        return {
            "error": self._result_error(result),
            "meta": self._failure_meta(result),
        }

    def _success_data(self, result: HistorySyncPresentationResult) -> dict[str, object]:
        return {
            "sync_run": self._present_run(self._required_run(result)),
            "counts": self._present_counts(self._required_counts(result)),
        }

    def _conflict_error(self, result: HistorySyncPresentationResult) -> dict[str, object]:
        sync_run = self._required_run(result)
        return {
            "code": HISTORY_SYNC_RUNNING_CODE,
            "message": HISTORY_SYNC_RUNNING_MESSAGE,
            "details": {
                "sync_run_id": sync_run.id,
                "started_at": self._present_datetime(sync_run.started_at),
            },
        }

    def _result_error(self, result: HistorySyncPresentationResult) -> dict[str, object]:
        if result.error_code is None or result.error_message is None:
            msg = "error sync result requires error_code and error_message"
            raise ValueError(msg)
        return {
            "code": result.error_code,
            "message": result.error_message,
            "details": dict(result.error_details),
        }

    def _failure_meta(self, result: HistorySyncPresentationResult) -> dict[str, object]:
        return {
            "sync_run": self._present_run(self._required_run(result)),
            "counts": self._present_counts(self._required_counts(result)),
        }

    def _present_run(self, sync_run: HistorySyncRunPresentationInput) -> dict[str, object]:
        return {
            "id": sync_run.id,
            "status": sync_run.status,
            "started_at": self._present_datetime(sync_run.started_at),
            "finished_at": self._present_datetime(sync_run.finished_at),
        }

    def _present_counts(self, counts: HistorySyncCountsPresentationInput) -> dict[str, object]:
        return {
            "processed_count": counts.processed_count,
            "inserted_count": counts.inserted_count,
            "updated_count": counts.updated_count,
            "saved_count": counts.saved_count,
            "skipped_count": counts.skipped_count,
            "failed_count": counts.failed_count,
            "degraded_count": counts.degraded_count,
        }

    def _present_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        normalized = value.astimezone(UTC) if value.tzinfo is not None else value
        return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")

    def _required_run(
        self, result: HistorySyncPresentationResult
    ) -> HistorySyncRunPresentationInput:
        if result.sync_run is None:
            msg = "sync_run is required"
            raise ValueError(msg)
        return result.sync_run

    def _required_counts(
        self, result: HistorySyncPresentationResult
    ) -> HistorySyncCountsPresentationInput:
        if result.counts is None:
            msg = "counts is required"
            raise ValueError(msg)
        return result.counts


__all__ = ["HistorySyncPresenter"]

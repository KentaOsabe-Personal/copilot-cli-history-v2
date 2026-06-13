from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from copilot_history.api.types import HistorySyncCountsPresentationInput
from copilot_history.types import NormalizedSession, ReadSuccessResult
from history_read_model.fake_repository import CopilotSessionRow, HistorySyncRunRow, SyncStatus
from history_read_model.repository_rows import build_copilot_session_write_input

SYNC_RUNNING_LOCK_KEY = "history-sync"


@dataclass(frozen=True)
class SyncRowsAssembly:
    session_rows: tuple[CopilotSessionRow, ...]
    counts: HistorySyncCountsPresentationInput
    sync_run_row: HistorySyncRunRow
    invalid_failures: Mapping[str, tuple[str, ...]]


def assemble_sync_rows(
    result: ReadSuccessResult,
    *,
    sync_run_id: str,
    started_at: datetime,
    finished_at: datetime,
    indexed_at: datetime,
    write_processed_count: int,
    write_inserted_count: int,
    write_updated_count: int,
    write_skipped_count: int,
    write_failed_count: int,
) -> SyncRowsAssembly:
    session_rows: list[CopilotSessionRow] = []
    workspace_only_count = 0
    invalid_failures: dict[str, tuple[str, ...]] = {}

    for session in result.sessions:
        candidate = build_copilot_session_write_input(
            session,
            source_fingerprint=_source_fingerprint(session),
            indexed_at=indexed_at,
        )
        if candidate.status == "persistable" and candidate.row is not None:
            session_rows.append(candidate.row)
        elif candidate.status == "workspace_only":
            workspace_only_count += 1
        else:
            invalid_failures[candidate.session_id] = candidate.error_reasons

    failed_count = len(invalid_failures) + write_failed_count
    degraded_count = sum(1 for row in session_rows if row.degraded)
    skipped_count = workspace_only_count + write_skipped_count
    counts = HistorySyncCountsPresentationInput(
        processed_count=len(result.sessions),
        inserted_count=write_inserted_count,
        updated_count=write_updated_count,
        saved_count=write_inserted_count + write_updated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        degraded_count=degraded_count,
    )
    status: SyncStatus = "completed_with_issues" if failed_count or degraded_count else "succeeded"

    return SyncRowsAssembly(
        session_rows=tuple(session_rows),
        counts=counts,
        sync_run_row=HistorySyncRunRow(
            sync_run_id=sync_run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            started_partition_date=started_at.date(),
            processed_count=counts.processed_count,
            inserted_count=counts.inserted_count,
            updated_count=counts.updated_count,
            saved_count=counts.saved_count,
            skipped_count=counts.skipped_count,
            failed_count=counts.failed_count,
            degraded_count=counts.degraded_count,
            failure_summary=_failure_summary(failed_count),
            degradation_summary=_degradation_summary(degraded_count),
            running_lock_key=None,
            indexed_at=indexed_at,
        ),
        invalid_failures=invalid_failures,
    )


def build_running_sync_run_row(
    *,
    sync_run_id: str,
    started_at: datetime,
    indexed_at: datetime,
) -> HistorySyncRunRow:
    return HistorySyncRunRow(
        sync_run_id=sync_run_id,
        status="running",
        started_at=started_at,
        finished_at=None,
        started_partition_date=started_at.date(),
        processed_count=0,
        inserted_count=0,
        updated_count=0,
        saved_count=0,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key=SYNC_RUNNING_LOCK_KEY,
        indexed_at=indexed_at,
    )


def build_failed_sync_run_row(
    *,
    sync_run_id: str,
    started_at: datetime,
    finished_at: datetime,
    indexed_at: datetime,
    counts: HistorySyncCountsPresentationInput,
    failure_summary: str,
) -> HistorySyncRunRow:
    return HistorySyncRunRow(
        sync_run_id=sync_run_id,
        status="failed",
        started_at=started_at,
        finished_at=finished_at,
        started_partition_date=started_at.date(),
        processed_count=counts.processed_count,
        inserted_count=counts.inserted_count,
        updated_count=counts.updated_count,
        saved_count=counts.saved_count,
        skipped_count=counts.skipped_count,
        failed_count=counts.failed_count,
        degraded_count=counts.degraded_count,
        failure_summary=failure_summary,
        degradation_summary=_degradation_summary(counts.degraded_count),
        running_lock_key=None,
        indexed_at=indexed_at,
    )


def _source_fingerprint(session: NormalizedSession) -> Mapping[str, object]:
    return {
        "session_id": session.session_id,
        "source_paths": dict(session.source_paths),
        "event_count": session.event_count,
        "message_snapshot_count": session.message_snapshot_count,
        "issue_count": session.issue_count,
        "updated_at": session.updated_at.isoformat() if session.updated_at is not None else None,
    }


def _failure_summary(failed_count: int) -> str | None:
    if failed_count == 0:
        return None
    suffix = "s" if failed_count != 1 else ""
    return f"{failed_count} session{suffix} failed validation"


def _degradation_summary(degraded_count: int) -> str | None:
    if degraded_count == 0:
        return None
    suffix = "s" if degraded_count != 1 else ""
    return f"{degraded_count} session{suffix} degraded"


__all__ = [
    "SYNC_RUNNING_LOCK_KEY",
    "SyncRowsAssembly",
    "assemble_sync_rows",
    "build_failed_sync_run_row",
    "build_running_sync_run_row",
]

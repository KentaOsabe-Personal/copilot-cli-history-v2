from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from history_read_model.bigquery_schema import (
    COPILOT_SESSIONS_BASE_NAME,
    HISTORY_SYNC_RUNS_BASE_NAME,
    BigQueryColumn,
    BigQueryTable,
    read_model_tables,
)


class ReadModelContractError(ValueError):
    """Raised when a fake repository row violates the BigQuery schema contract."""


@dataclass(frozen=True)
class CopilotSessionRow:
    session_id: str
    source_format: str
    source_state: str
    created_at_source: datetime | None
    updated_at_source: datetime | None
    source_partition_date: date
    cwd: str | None
    git_root: str | None
    repository: str | None
    branch: str | None
    selected_model: str | None
    event_count: int
    message_snapshot_count: int
    issue_count: int
    message_count: int
    activity_count: int
    degraded: bool
    conversation_preview: str | None
    source_paths: Mapping[str, object]
    source_fingerprint: Mapping[str, object]
    summary_payload: Mapping[str, object]
    detail_payload: Mapping[str, object]
    search_text: str
    search_text_version: int
    indexed_at: datetime


SyncStatus = Literal["running", "succeeded", "failed", "completed_with_issues"]


@dataclass(frozen=True)
class HistorySyncRunRow:
    sync_run_id: str
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None
    started_partition_date: date
    processed_count: int
    inserted_count: int
    updated_count: int
    saved_count: int
    skipped_count: int
    failed_count: int
    degraded_count: int
    failure_summary: str | None
    degradation_summary: str | None
    running_lock_key: str | None
    indexed_at: datetime


class FakeBigQueryReadModelRepository:
    def __init__(self, schema_tables: Sequence[BigQueryTable] | None = None) -> None:
        tables = tuple(schema_tables) if schema_tables is not None else read_model_tables()
        self._tables_by_base_name = {table.base_name: table for table in tables}
        self._sessions_by_id: dict[str, CopilotSessionRow] = {}
        self._sync_runs_by_id: dict[str, HistorySyncRunRow] = {}

    def save_session(self, row: CopilotSessionRow) -> None:
        table = self._table(COPILOT_SESSIONS_BASE_NAME)
        _validate_row_contract(table, row)
        self._sessions_by_id[row.session_id] = row

    def save_sync_run(self, row: HistorySyncRunRow) -> None:
        table = self._table(HISTORY_SYNC_RUNS_BASE_NAME)
        _validate_row_contract(table, row)
        _validate_sync_lifecycle(table, row)
        self._sync_runs_by_id[row.sync_run_id] = row

    def get_session(self, session_id: str) -> CopilotSessionRow | None:
        return self._sessions_by_id.get(session_id)

    def get_sync_run(self, sync_run_id: str) -> HistorySyncRunRow | None:
        return self._sync_runs_by_id.get(sync_run_id)

    def list_sessions(self) -> tuple[CopilotSessionRow, ...]:
        return tuple(self._sessions_by_id.values())

    def list_sync_runs(self) -> tuple[HistorySyncRunRow, ...]:
        return tuple(self._sync_runs_by_id.values())

    def _table(self, base_name: str) -> BigQueryTable:
        try:
            return self._tables_by_base_name[base_name]
        except KeyError as exc:
            raise ReadModelContractError(f"{base_name} schema table is not configured") from exc


def _validate_row_contract(table: BigQueryTable, row: object) -> None:
    values = _row_values(row)
    errors: list[str] = []

    for column in table.columns:
        value_missing = column.name not in values
        value = values.get(column.name)
        qualified_name = f"{table.base_name}.{column.name}"

        if value_missing:
            if column.mode == "REQUIRED":
                errors.append(f"{qualified_name} is required by schema but missing from row")
            continue

        if column.mode == "REQUIRED" and value is None:
            errors.append(f"{qualified_name} is required")
            continue

        if value is None:
            continue

        _validate_allowed_values(column, value, qualified_name, errors)
        _validate_non_negative(column, value, qualified_name, errors)
        _validate_json_object(column, value, qualified_name, errors)

    if errors:
        raise ReadModelContractError("; ".join(errors))


def _validate_allowed_values(
    column: BigQueryColumn,
    value: object,
    qualified_name: str,
    errors: list[str],
) -> None:
    if column.allowed_values and value not in column.allowed_values:
        errors.append(f"{qualified_name} must be one of {column.allowed_values}")


def _validate_non_negative(
    column: BigQueryColumn,
    value: object,
    qualified_name: str,
    errors: list[str],
) -> None:
    if not column.non_negative:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{qualified_name} must be non-negative")


def _validate_json_object(
    column: BigQueryColumn,
    value: object,
    qualified_name: str,
    errors: list[str],
) -> None:
    if column.json_object and not isinstance(value, Mapping):
        errors.append(f"{qualified_name} must be a JSON object mapping")


def _validate_sync_lifecycle(table: BigQueryTable, row: HistorySyncRunRow) -> None:
    errors: list[str] = []

    if row.status == table.running_status and not row.running_lock_key:
        errors.append(f"{table.base_name}.running_lock_key is required for running status")

    if row.status in table.terminal_statuses and row.finished_at is None:
        errors.append(f"{table.base_name}.finished_at is required for terminal status")

    if table.saved_count_equals is not None:
        inserted_field, updated_field = table.saved_count_equals
        expected_saved_count = getattr(row, inserted_field) + getattr(row, updated_field)
        if row.saved_count != expected_saved_count:
            errors.append(
                f"{table.base_name}.saved_count must equal {inserted_field} + {updated_field}"
            )

    if errors:
        raise ReadModelContractError("; ".join(errors))


def _row_values(row: object) -> Mapping[str, Any]:
    if not hasattr(row, "__dict__"):
        raise ReadModelContractError(f"Unsupported read model row type: {type(row).__name__}")
    return row.__dict__

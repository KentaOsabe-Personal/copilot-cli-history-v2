from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

from history_read_model.bigquery_errors import classify_bigquery_exception
from history_read_model.bigquery_settings import BigQueryReadModelSettings
from history_read_model.bigquery_sql import (
    BigQuerySql,
    build_running_sync_run_query,
    build_session_detail_query,
    build_session_list_query,
    build_session_merge_query,
    build_session_metadata_query,
    build_sync_run_start_query,
    build_sync_run_upsert_query,
)
from history_read_model.fake_repository import CopilotSessionRow, HistorySyncRunRow
from history_read_model.repository import (
    RepositoryExecutionOptions,
    SessionDetailResult,
    SessionListCriteria,
    SessionListResult,
    SyncRunConflict,
    SyncRunLookupResult,
    SyncRunResult,
    SyncRunStartResult,
    SyncWriteResult,
    validate_repository_options,
    validate_session_id,
    validate_session_list_criteria,
)
from history_read_model.repository_write_planner import (
    ExistingSessionMetadata,
    SessionWriteInput,
    plan_sync_write,
)


class BigQuerySessionReadModelRepository:
    def __init__(
        self,
        *,
        client: Any,
        settings: BigQueryReadModelSettings,
        staging_table_suffix: str = "session_write_stage",
    ) -> None:
        self._client = client
        self._settings = settings
        self._staging_table_suffix = staging_table_suffix

    def list_sessions(
        self,
        criteria: SessionListCriteria,
        options: RepositoryExecutionOptions,
    ) -> SessionListResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options) or validate_session_list_criteria(
            criteria
        )
        if error is not None:
            return SessionListResult.failure(error)

        query = build_session_list_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            criteria=criteria,
            options=execution_options,
        )
        if execution_options.dry_run:
            return SessionListResult.success(
                (),
                dry_run=True,
                planned_operations=("list_query",),
            )

        try:
            rows = self._run_query(query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SessionListResult.failure(classify_bigquery_exception(exc))

        return SessionListResult.success(_mapping_payloads(rows, "summary_payload"))

    def get_session_detail(
        self,
        session_id: str,
        options: RepositoryExecutionOptions,
    ) -> SessionDetailResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options) or validate_session_id(session_id)
        if error is not None:
            return SessionDetailResult.failure(error)

        query = build_session_detail_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            session_id=session_id,
            options=execution_options,
        )
        if execution_options.dry_run:
            return SessionDetailResult(
                ok=True,
                found=False,
                session_id=session_id,
                dry_run=True,
                planned_operations=("detail_lookup",),
            )

        try:
            rows = self._run_query(query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SessionDetailResult.failure(classify_bigquery_exception(exc))

        for row in rows:
            payload = _mapping_value(_row_value(row, "detail_payload"))
            if payload is not None:
                return SessionDetailResult.success(payload, session_id=session_id)
        return SessionDetailResult.not_found(session_id)

    def save_sessions(
        self,
        rows: Sequence[SessionWriteInput],
        options: RepositoryExecutionOptions,
    ) -> SyncWriteResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options)
        if error is not None:
            return SyncWriteResult.failure(error)

        try:
            existing_metadata = self._load_existing_metadata(rows, execution_options)
            plan = plan_sync_write(rows, existing_metadata=existing_metadata)
            result = plan.to_result(dry_run=execution_options.dry_run)
            if execution_options.dry_run or not plan.rows_for_merge:
                return result

            staging_table_id = self._staging_table_id()
            insert_errors = self._client.insert_rows_json(
                staging_table_id,
                [_session_row_json(row) for row in plan.rows_for_merge],
            )
            if insert_errors:
                raise RuntimeError(f"BigQuery staging insert failed: {insert_errors!r}")
            merge_query = build_session_merge_query(
                project_id=self._settings.project_id,
                dataset_id=self._settings.dataset_id,
                table_prefix=self._settings.table_prefix,
                staging_table_id=staging_table_id,
                session_ids=tuple(row.session_id for row in plan.rows_for_merge),
                partition_dates=tuple(row.source_partition_date for row in plan.rows_for_merge),
                options=execution_options,
            )
            self._run_query(merge_query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SyncWriteResult.failure(classify_bigquery_exception(exc))

        return result

    def save_sync_run(
        self,
        row: HistorySyncRunRow,
        options: RepositoryExecutionOptions,
    ) -> SyncRunResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options)
        if error is not None:
            return SyncRunResult.failure(error)

        query = build_sync_run_upsert_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            row=row,
            options=execution_options,
        )
        if execution_options.dry_run:
            return SyncRunResult.success(
                row.sync_run_id,
                dry_run=True,
                planned_operations=("sync_run_upsert",),
            )

        try:
            self._run_query(query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SyncRunResult.failure(classify_bigquery_exception(exc))
        return SyncRunResult.success(row.sync_run_id)

    def start_sync_run(
        self,
        row: HistorySyncRunRow,
        options: RepositoryExecutionOptions,
    ) -> SyncRunStartResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options)
        if error is not None:
            return SyncRunStartResult.failure(error)

        query = build_sync_run_start_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            row=row,
            options=execution_options,
        )
        if execution_options.dry_run:
            return SyncRunStartResult.started_success(
                row.sync_run_id,
                dry_run=True,
                planned_operations=("atomic_sync_start",),
            )

        try:
            rows = self._run_query(query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SyncRunStartResult.failure(classify_bigquery_exception(exc))

        for result_row in rows:
            started = _row_value(result_row, "started")
            sync_run_id = _row_value(result_row, "sync_run_id")
            started_at = _datetime_value(_row_value(result_row, "started_at"))
            if started is True and isinstance(sync_run_id, str):
                return SyncRunStartResult.started_success(sync_run_id)
            if started is False and isinstance(sync_run_id, str) and started_at is not None:
                return SyncRunStartResult.conflict_result(
                    SyncRunConflict(sync_run_id=sync_run_id, started_at=started_at)
                )
        return SyncRunStartResult.failure(
            classify_bigquery_exception(RuntimeError("BigQuery sync start returned no result"))
        )

    def finish_sync_run(
        self,
        row: HistorySyncRunRow,
        options: RepositoryExecutionOptions,
    ) -> SyncRunResult:
        return self.save_sync_run(row, options)

    def find_running_sync_run(
        self,
        options: RepositoryExecutionOptions,
    ) -> SyncRunLookupResult:
        execution_options = _options_with_defaults(options, self._settings)
        error = validate_repository_options(execution_options)
        if error is not None:
            return SyncRunLookupResult.failure(error)

        query = build_running_sync_run_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            options=execution_options,
        )
        if execution_options.dry_run:
            return SyncRunLookupResult(
                ok=True,
                found=False,
                dry_run=True,
                planned_operations=("running_sync_lookup",),
            )

        try:
            rows = self._run_query(query, execution_options)
        except Exception as exc:  # noqa: BLE001
            return SyncRunLookupResult.failure(classify_bigquery_exception(exc))

        for row in rows:
            sync_run_id = _row_value(row, "sync_run_id")
            started_at = _datetime_value(_row_value(row, "started_at"))
            if isinstance(sync_run_id, str):
                return SyncRunLookupResult.success(
                    sync_run_id,
                    started_at=started_at,
                )
        return SyncRunLookupResult.not_found()

    def _load_existing_metadata(
        self,
        rows: Sequence[SessionWriteInput],
        options: RepositoryExecutionOptions,
    ) -> Mapping[str, ExistingSessionMetadata]:
        candidate_rows = _candidate_copilot_rows(rows)
        if not candidate_rows:
            return {}

        query = build_session_metadata_query(
            project_id=self._settings.project_id,
            dataset_id=self._settings.dataset_id,
            table_prefix=self._settings.table_prefix,
            session_ids=tuple(row.session_id for row in candidate_rows),
            partition_dates=tuple(row.source_partition_date for row in candidate_rows),
            options=options,
        )
        metadata_rows = self._run_query(query, options)
        return {
            metadata.session_id: metadata
            for metadata in (_metadata_from_row(row) for row in metadata_rows)
            if metadata is not None
        }

    def _run_query(
        self,
        query: BigQuerySql,
        options: RepositoryExecutionOptions,
    ) -> tuple[object, ...]:
        job = self._client.query(
            query.sql,
            job_config=_job_config(query),
            location=options.location or self._settings.location,
        )
        return tuple(job.result())

    def _staging_table_id(self) -> str:
        return (
            f"{self._settings.project_id}."
            f"{self._settings.dataset_id}."
            f"{self._settings.table_prefix}{self._staging_table_suffix}"
        )


def _options_with_defaults(
    options: RepositoryExecutionOptions,
    settings: BigQueryReadModelSettings,
) -> RepositoryExecutionOptions:
    maximum_bytes_billed = (
        options.maximum_bytes_billed
        if options.maximum_bytes_billed is not None
        else settings.maximum_bytes_billed_default
    )
    return RepositoryExecutionOptions(
        dry_run=options.dry_run,
        maximum_bytes_billed=maximum_bytes_billed,
        location=options.location or settings.location,
    )


def _job_config(query: BigQuerySql) -> object:
    try:
        from google.cloud import bigquery
    except Exception:  # noqa: BLE001
        return SimpleNamespace(
            dry_run=query.dry_run,
            maximum_bytes_billed=query.maximum_bytes_billed,
            query_parameters=query.parameters,
        )

    config_kwargs: dict[str, object] = {
        "dry_run": query.dry_run,
        "query_parameters": [
            _to_bigquery_parameter(bigquery, parameter.name, parameter.type_, parameter.value)
            for parameter in query.parameters
        ],
    }
    if query.maximum_bytes_billed is not None:
        config_kwargs["maximum_bytes_billed"] = query.maximum_bytes_billed
    return bigquery.QueryJobConfig(**config_kwargs)


def _to_bigquery_parameter(
    bigquery: Any,
    name: str,
    parameter_type: str | None,
    value: object,
) -> object:
    if parameter_type == "ARRAY<STRING>":
        array_values = list(value) if isinstance(value, tuple) else []
        return bigquery.ArrayQueryParameter(name, "STRING", array_values)
    return bigquery.ScalarQueryParameter(
        name,
        parameter_type,
        cast(Any, value),
    )


def _metadata_from_row(row: object) -> ExistingSessionMetadata | None:
    session_id = _row_value(row, "session_id")
    source_fingerprint = _mapping_value(_row_value(row, "source_fingerprint"))
    search_text_version = _row_value(row, "search_text_version")
    if (
        not isinstance(session_id, str)
        or source_fingerprint is None
        or not isinstance(search_text_version, int)
        or isinstance(search_text_version, bool)
    ):
        return None
    return ExistingSessionMetadata(
        session_id=session_id,
        source_fingerprint=source_fingerprint,
        search_text_version=search_text_version,
    )


def _candidate_copilot_rows(rows: Sequence[SessionWriteInput]) -> tuple[CopilotSessionRow, ...]:
    candidate_rows: list[CopilotSessionRow] = []
    for row in rows:
        if isinstance(row, CopilotSessionRow):
            candidate_rows.append(row)
            continue
        nested_row = getattr(row, "row", None)
        if isinstance(nested_row, CopilotSessionRow):
            candidate_rows.append(nested_row)
    return tuple(candidate_rows)


def _mapping_payloads(rows: Sequence[object], key: str) -> tuple[Mapping[str, object], ...]:
    payloads: list[Mapping[str, object]] = []
    for row in rows:
        payload = _mapping_value(_row_value(row, key))
        if payload is not None:
            payloads.append(payload)
    return tuple(payloads)


def _mapping_value(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _datetime_value(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _row_value(row: object, key: str) -> object:
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, None)


def _session_row_json(row: CopilotSessionRow) -> dict[str, object]:
    return asdict(row)


__all__ = ["BigQuerySessionReadModelRepository"]

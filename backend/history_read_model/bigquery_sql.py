from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from history_read_model.bigquery_schema import (
    COPILOT_SESSIONS_BASE_NAME,
    HISTORY_SYNC_RUNS_BASE_NAME,
    table_by_base_name,
)
from history_read_model.fake_repository import HistorySyncRunRow
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


@dataclass(frozen=True)
class QueryParameter:
    name: str
    value: object
    type_: str | None = None


@dataclass(frozen=True)
class BigQuerySql:
    sql: str
    parameters: tuple[QueryParameter, ...]
    dry_run: bool
    maximum_bytes_billed: int | None

    def parameter_value(self, name: str) -> object:
        for parameter in self.parameters:
            if parameter.name == name:
                return parameter.value
        raise KeyError(name)


def build_session_list_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    criteria: SessionListCriteria,
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, COPILOT_SESSIONS_BASE_NAME)
    source_predicates = [
        "source_partition_date BETWEEN @from_date AND @to_date",
    ]
    candidate_predicates = [
        "display_time IS NOT NULL",
        "display_time BETWEEN @from_datetime AND @to_datetime",
    ]
    parameters = [
        QueryParameter("from_datetime", criteria.from_datetime, "TIMESTAMP"),
        QueryParameter("to_datetime", criteria.to_datetime, "TIMESTAMP"),
        QueryParameter("from_date", _date_value(criteria.from_datetime), "DATE"),
        QueryParameter("to_date", _date_value(criteria.to_datetime), "DATE"),
    ]

    search_term = _normalized_search_parameter(criteria.search_term)
    if search_term is not None:
        candidate_predicates.append(
            "(LOWER(search_text) LIKE @search_term "
            "OR LOWER(COALESCE(cwd, '')) LIKE @search_term)"
        )
        parameters.append(QueryParameter("search_term", search_term, "STRING"))

    sql = f"""
WITH source_rows AS (
  SELECT
    session_id,
    search_text,
    cwd,
    summary_payload,
    COALESCE(updated_at_source, created_at_source) AS display_time
  FROM {table}
  WHERE {" AND ".join(source_predicates)}
),
candidates AS (
  SELECT
    session_id,
    summary_payload,
    display_time
  FROM source_rows
  WHERE {" AND ".join(candidate_predicates)}
)
SELECT summary_payload
FROM candidates
ORDER BY display_time DESC, session_id ASC
""".strip()

    if criteria.limit is not None:
        sql = f"{sql}\nLIMIT @limit"
        parameters.append(QueryParameter("limit", criteria.limit, "INT64"))

    return BigQuerySql(
        sql=sql,
        parameters=tuple(parameters),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_session_detail_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    session_id: str,
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, COPILOT_SESSIONS_BASE_NAME)
    return BigQuerySql(
        sql=f"""
SELECT detail_payload
FROM {table}
WHERE session_id = @session_id
  AND source_partition_date BETWEEN DATE '1970-01-01' AND CURRENT_DATE()
LIMIT 1
""".strip(),
        parameters=(QueryParameter("session_id", session_id, "STRING"),),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_session_metadata_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    session_ids: tuple[str, ...],
    partition_dates: tuple[date, ...],
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, COPILOT_SESSIONS_BASE_NAME)
    from_date, to_date = _partition_date_bounds(partition_dates)
    return BigQuerySql(
        sql=f"""
SELECT session_id, source_fingerprint, search_text_version
FROM {table}
WHERE source_partition_date BETWEEN @from_date AND @to_date
  AND session_id IN UNNEST(@session_ids)
""".strip(),
        parameters=(
            QueryParameter("session_ids", session_ids, "ARRAY<STRING>"),
            QueryParameter("from_date", from_date, "DATE"),
            QueryParameter("to_date", to_date, "DATE"),
        ),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_session_merge_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    staging_table_id: str,
    session_ids: tuple[str, ...],
    partition_dates: tuple[date, ...],
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    target = _qualified_table(project_id, dataset_id, table_prefix, COPILOT_SESSIONS_BASE_NAME)
    source = f"""
(
  SELECT * FROM `{staging_table_id}`
  WHERE session_id IN UNNEST(@session_ids)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY indexed_at DESC) = 1
)
""".strip()
    from_date, to_date = _partition_date_bounds(partition_dates)
    columns = tuple(
        column.name for column in table_by_base_name(COPILOT_SESSIONS_BASE_NAME).columns
    )
    update_columns = tuple(column for column in columns if column != "session_id")
    update_clause = ",\n    ".join(
        f"{column} = source.{column}" for column in update_columns
    )
    insert_columns = ", ".join(columns)
    insert_values = ", ".join(f"source.{column}" for column in columns)
    return BigQuerySql(
        sql=f"""
MERGE {target} AS target
USING {source} AS source
ON target.session_id = source.session_id
  AND target.source_partition_date BETWEEN @from_date AND @to_date
WHEN MATCHED THEN
  UPDATE SET
    {update_clause}
WHEN NOT MATCHED THEN
  INSERT ({insert_columns})
  VALUES ({insert_values})
""".strip(),
        parameters=(
            QueryParameter("session_ids", session_ids, "ARRAY<STRING>"),
            QueryParameter("from_date", from_date, "DATE"),
            QueryParameter("to_date", to_date, "DATE"),
        ),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_sync_run_upsert_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    row: HistorySyncRunRow,
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, HISTORY_SYNC_RUNS_BASE_NAME)
    columns = tuple(
        column.name for column in table_by_base_name(HISTORY_SYNC_RUNS_BASE_NAME).columns
    )
    source_columns = ",\n    ".join(f"@{column} AS {column}" for column in columns)
    update_columns = tuple(column for column in columns if column != "sync_run_id")
    update_clause = ",\n    ".join(
        f"{column} = source.{column}" for column in update_columns
    )
    insert_columns = ", ".join(columns)
    insert_values = ", ".join(f"source.{column}" for column in columns)
    return BigQuerySql(
        sql=f"""
MERGE {table} AS target
USING (
  SELECT
    {source_columns}
) AS source
ON target.sync_run_id = source.sync_run_id
WHEN MATCHED THEN
  UPDATE SET
    {update_clause}
WHEN NOT MATCHED THEN
  INSERT ({insert_columns})
  VALUES ({insert_values})
""".strip(),
        parameters=tuple(
            QueryParameter(
                column,
                getattr(row, column),
                table_by_base_name(HISTORY_SYNC_RUNS_BASE_NAME).column_map[column].type,
            )
            for column in columns
        ),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_sync_run_start_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    row: HistorySyncRunRow,
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, HISTORY_SYNC_RUNS_BASE_NAME)
    columns = tuple(
        column.name for column in table_by_base_name(HISTORY_SYNC_RUNS_BASE_NAME).columns
    )
    source_columns = ",\n      ".join(f"@{column} AS {column}" for column in columns)
    insert_columns = ", ".join(columns)
    insert_values = ", ".join(f"source.{column}" for column in columns)
    parameters = tuple(
        QueryParameter(
            column,
            getattr(row, column),
            table_by_base_name(HISTORY_SYNC_RUNS_BASE_NAME).column_map[column].type,
        )
        for column in columns
    )
    return BigQuerySql(
        sql=f"""
DECLARE running_sync_run_id STRING DEFAULT (
  SELECT sync_run_id
  FROM {table}
  WHERE status = @running_status
    AND running_lock_key IS NOT NULL
  ORDER BY started_at ASC, sync_run_id ASC
  LIMIT 1
);
DECLARE running_started_at TIMESTAMP DEFAULT (
  SELECT started_at
  FROM {table}
  WHERE sync_run_id = running_sync_run_id
  LIMIT 1
);

IF running_sync_run_id IS NULL THEN
  MERGE {table} AS target
  USING (
    SELECT
      {source_columns}
  ) AS source
  ON target.sync_run_id = source.sync_run_id
  WHEN NOT MATCHED THEN
    INSERT ({insert_columns})
    VALUES ({insert_values});
  SELECT TRUE AS started, @sync_run_id AS sync_run_id, @started_at AS started_at;
ELSE
  SELECT FALSE AS started, running_sync_run_id AS sync_run_id, running_started_at AS started_at;
END IF
""".strip(),
        parameters=(
            *parameters,
            QueryParameter("running_status", "running", "STRING"),
        ),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def build_running_sync_run_query(
    *,
    project_id: str,
    dataset_id: str,
    table_prefix: str,
    options: RepositoryExecutionOptions,
) -> BigQuerySql:
    table = _qualified_table(project_id, dataset_id, table_prefix, HISTORY_SYNC_RUNS_BASE_NAME)
    return BigQuerySql(
        sql=f"""
SELECT sync_run_id, started_at
FROM {table}
WHERE status = @running_status
  AND running_lock_key IS NOT NULL
ORDER BY started_at ASC, sync_run_id ASC
LIMIT 1
""".strip(),
        parameters=(QueryParameter("running_status", "running", "STRING"),),
        dry_run=options.dry_run,
        maximum_bytes_billed=options.maximum_bytes_billed,
    )


def _qualified_table(project_id: str, dataset_id: str, table_prefix: str, base_name: str) -> str:
    return f"`{project_id}.{dataset_id}.{table_prefix}{base_name}`"


def _date_value(value: object) -> date | None:
    return value.date() if hasattr(value, "date") else None


def _partition_date_bounds(partition_dates: tuple[date, ...]) -> tuple[date, date]:
    if not partition_dates:
        raise ValueError("partition_dates must not be empty")
    return min(partition_dates), max(partition_dates)


def _normalized_search_parameter(search_term: str | None) -> str | None:
    if search_term is None:
        return None
    normalized = " ".join(search_term.split()).lower()
    if normalized == "":
        return None
    return f"%{normalized}%"


__all__ = [
    "BigQuerySql",
    "QueryParameter",
    "build_running_sync_run_query",
    "build_session_detail_query",
    "build_session_list_query",
    "build_session_merge_query",
    "build_session_metadata_query",
    "build_sync_run_start_query",
    "build_sync_run_upsert_query",
]

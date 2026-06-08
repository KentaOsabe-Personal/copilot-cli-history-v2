from __future__ import annotations

import re

from history_read_model.bigquery_schema import BigQueryColumn, BigQueryTable, read_model_tables
from history_read_model.bigquery_settings import BigQueryReadModelSettings

_IDENTIFIER_PART_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def build_create_dataset_sql(settings: BigQueryReadModelSettings) -> str:
    dataset_identifier = _quote_fully_qualified_identifier(settings.project_id, settings.dataset_id)
    location = _sql_string_literal(settings.location)
    return f"CREATE SCHEMA IF NOT EXISTS {dataset_identifier}\nOPTIONS(location = {location});"


def build_create_table_sql(settings: BigQueryReadModelSettings, table: BigQueryTable) -> str:
    table_identifier = _quote_fully_qualified_identifier(
        settings.project_id,
        settings.dataset_id,
        table.name,
    )
    column_sql = ",\n".join(f"  {_build_column_sql(column)}" for column in table.columns)
    statements = [
        f"CREATE TABLE IF NOT EXISTS {table_identifier} (",
        column_sql,
        ")",
    ]
    if table.partition_by is not None:
        statements.append(f"PARTITION BY {table.partition_by}")
    if table.cluster_by:
        statements.append(f"CLUSTER BY {', '.join(table.cluster_by)}")
    statements.append(
        "OPTIONS(require_partition_filter = "
        f"{'TRUE' if table.require_partition_filter else 'FALSE'});"
    )
    return "\n".join(statements)


def build_schema_metadata_sql(settings: BigQueryReadModelSettings) -> str:
    tables = read_model_tables(table_prefix=settings.table_prefix)
    table_names = ", ".join(_sql_string_literal(table.name) for table in tables)
    columns_view = _quote_fully_qualified_identifier(
        settings.project_id,
        settings.dataset_id,
        "INFORMATION_SCHEMA",
        "COLUMNS",
    )
    options_view = _quote_fully_qualified_identifier(
        settings.project_id,
        settings.dataset_id,
        "INFORMATION_SCHEMA",
        "TABLE_OPTIONS",
    )
    return (
        "SELECT\n"
        "  'column' AS metadata_kind,\n"
        "  table_name,\n"
        "  column_name,\n"
        "  data_type,\n"
        "  is_nullable,\n"
        "  is_partitioning_column,\n"
        "  clustering_ordinal_position,\n"
        "  CAST(NULL AS STRING) AS option_name,\n"
        "  CAST(NULL AS STRING) AS option_value\n"
        f"FROM {columns_view}\n"
        f"WHERE table_name IN ({table_names})\n"
        "UNION ALL\n"
        "SELECT\n"
        "  'option' AS metadata_kind,\n"
        "  table_name,\n"
        "  CAST(NULL AS STRING) AS column_name,\n"
        "  CAST(NULL AS STRING) AS data_type,\n"
        "  CAST(NULL AS STRING) AS is_nullable,\n"
        "  CAST(NULL AS STRING) AS is_partitioning_column,\n"
        "  CAST(NULL AS INT64) AS clustering_ordinal_position,\n"
        "  option_name,\n"
        "  option_value\n"
        f"FROM {options_view}\n"
        f"WHERE table_name IN ({table_names});"
    )


def _build_column_sql(column: BigQueryColumn) -> str:
    nullable = "" if column.mode == "NULLABLE" else " NOT NULL"
    return f"{_quote_column_name(column.name)} {column.type}{nullable}"


def _quote_fully_qualified_identifier(*parts: str) -> str:
    for part in parts:
        if not _IDENTIFIER_PART_PATTERN.fullmatch(part):
            raise ValueError(f"Unsafe BigQuery identifier part: {part!r}")
    return "`" + ".".join(parts) + "`"


def _quote_column_name(name: str) -> str:
    if not _IDENTIFIER_PART_PATTERN.fullmatch(name):
        raise ValueError(f"Unsafe BigQuery column name: {name!r}")
    return f"`{name}`"


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

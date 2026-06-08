from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from history_read_model.bigquery_schema import BigQueryTable


@dataclass(frozen=True)
class SchemaDiff:
    missing: tuple[str, ...]
    incompatible: tuple[str, ...]
    extra: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return not self.missing and not self.incompatible


def compare_metadata(
    expected: tuple[BigQueryTable, ...],
    actual_columns: Sequence[Mapping[str, object]],
    actual_options: Sequence[Mapping[str, object]],
) -> SchemaDiff:
    actual_column_map = _actual_column_map(actual_columns)
    expected_table_names = {table.name for table in expected}
    missing: list[str] = []
    incompatible: list[str] = []
    extra: list[str] = []

    for table in expected:
        _compare_columns(table, actual_column_map, missing, incompatible)
        _compare_partition(table, actual_column_map, incompatible)
        _compare_clustering(table, actual_column_map, incompatible)
        _compare_require_partition_filter(table, actual_options, incompatible)

    expected_columns = {
        (table.name, column.name)
        for table in expected
        for column in table.columns
    }
    for table_name, column_name in sorted(actual_column_map):
        if table_name in expected_table_names and (table_name, column_name) not in expected_columns:
            extra.append(f"{table_name}.{column_name}")

    return SchemaDiff(
        missing=tuple(missing),
        incompatible=tuple(incompatible),
        extra=tuple(extra),
    )


def _compare_columns(
    table: BigQueryTable,
    actual_column_map: dict[tuple[str, str], Mapping[str, object]],
    missing: list[str],
    incompatible: list[str],
) -> None:
    for expected_column in table.columns:
        actual_column = actual_column_map.get((table.name, expected_column.name))
        qualified_name = f"{table.name}.{expected_column.name}"
        if actual_column is None:
            missing.append(qualified_name)
            continue

        actual_type = _string_value(actual_column.get("data_type")).upper()
        if actual_type != expected_column.type:
            incompatible.append(
                f"{qualified_name} type expected {expected_column.type} but was {actual_type}"
            )

        actual_mode = _mode_from_nullable(actual_column.get("is_nullable"))
        if actual_mode != expected_column.mode:
            incompatible.append(
                f"{qualified_name} mode expected {expected_column.mode} but was {actual_mode}"
            )


def _compare_partition(
    table: BigQueryTable,
    actual_column_map: dict[tuple[str, str], Mapping[str, object]],
    incompatible: list[str],
) -> None:
    if table.partition_by is None:
        return

    actual_partition_columns = tuple(
        column_name
        for actual_table_name, column_name in sorted(actual_column_map)
        if actual_table_name == table.name
        and _is_truthy_metadata_value(
            actual_column_map[(actual_table_name, column_name)].get("is_partitioning_column")
        )
    )
    expected = table.partition_by
    if actual_partition_columns != (expected,):
        actual_label = "absent" if not actual_partition_columns else str(actual_partition_columns)
        incompatible.append(f"{table.name} partition expected {expected} but was {actual_label}")


def _compare_clustering(
    table: BigQueryTable,
    actual_column_map: dict[tuple[str, str], Mapping[str, object]],
    incompatible: list[str],
) -> None:
    actual_cluster_pairs: list[tuple[int, str]] = []
    for (actual_table_name, column_name), actual_column in actual_column_map.items():
        if actual_table_name != table.name:
            continue
        position = _int_or_none(actual_column.get("clustering_ordinal_position"))
        if position is not None:
            actual_cluster_pairs.append((position, column_name))

    actual_cluster_by = tuple(column_name for _, column_name in sorted(actual_cluster_pairs))
    if actual_cluster_by != table.cluster_by:
        incompatible.append(
            f"{table.name} clustering expected {table.cluster_by} but was {actual_cluster_by}"
        )


def _compare_require_partition_filter(
    table: BigQueryTable,
    actual_options: Sequence[Mapping[str, object]],
    incompatible: list[str],
) -> None:
    expected_value = "true" if table.require_partition_filter else "false"
    actual_value = None
    for row in actual_options:
        if (
            _string_value(row.get("table_name")) == table.name
            and _string_value(row.get("option_name")) == "require_partition_filter"
        ):
            actual_value = _normalize_option_value(row.get("option_value"))
            break

    if actual_value != expected_value:
        actual_label = "absent" if actual_value is None else actual_value
        incompatible.append(
            f"{table.name} option require_partition_filter expected "
            f"{expected_value} but was {actual_label}"
        )


def _actual_column_map(
    actual_columns: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str], Mapping[str, object]]:
    return {
        (_string_value(row.get("table_name")), _string_value(row.get("column_name"))): row
        for row in actual_columns
    }


def _mode_from_nullable(value: object) -> str:
    return "NULLABLE" if _string_value(value).upper() == "YES" else "REQUIRED"


def _is_truthy_metadata_value(value: object) -> bool:
    return _string_value(value).strip().lower() in {"yes", "true", "1"}


def _normalize_option_value(value: object) -> str:
    normalized = _string_value(value).strip().strip('"').strip("'").lower()
    if normalized in {"true", "1"}:
        return "true"
    if normalized in {"false", "0"}:
        return "false"
    return normalized


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer metadata value: {value!r}")


def _string_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)

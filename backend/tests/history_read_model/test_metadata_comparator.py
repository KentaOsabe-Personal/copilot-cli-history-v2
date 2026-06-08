from collections.abc import Mapping

from history_read_model.bigquery_schema import read_model_tables
from history_read_model.metadata_comparator import compare_metadata


def _expected_columns() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for table in read_model_tables(table_prefix="dev_"):
        for column in table.columns:
            rows.append(
                {
                    "table_name": table.name,
                    "column_name": column.name,
                    "data_type": column.type,
                    "is_nullable": "NO" if column.mode == "REQUIRED" else "YES",
                    "is_partitioning_column": "YES"
                    if column.name == table.partition_by
                    else "NO",
                    "clustering_ordinal_position": _cluster_position(table.cluster_by, column.name),
                }
            )
    return rows


def _expected_options() -> list[dict[str, object]]:
    return [
        {
            "table_name": table.name,
            "option_name": "require_partition_filter",
            "option_value": "true" if table.require_partition_filter else "false",
        }
        for table in read_model_tables(table_prefix="dev_")
    ]


def _cluster_position(cluster_by: tuple[str, ...], column_name: str) -> int | None:
    if column_name not in cluster_by:
        return None
    return cluster_by.index(column_name) + 1


def _without_column(
    rows: list[dict[str, object]],
    *,
    table_name: str,
    column_name: str,
) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if row["table_name"] != table_name or row["column_name"] != column_name
    ]


# 概要・目的: BigQuery metadata が schema 契約と一致すると compatible になることを守る。
# テストケース: schema 定義から作った COLUMNS / TABLE_OPTIONS 相当の rows を比較する。
# 期待値: missing / incompatible / extra が空で compatible true になる。
def test_compare_metadata_returns_compatible_for_matching_schema() -> None:
    diff = compare_metadata(
        expected=read_model_tables(table_prefix="dev_"),
        actual_columns=_expected_columns(),
        actual_options=_expected_options(),
    )

    assert diff.compatible is True
    assert diff.missing == ()
    assert diff.incompatible == ()
    assert diff.extra == ()


# 概要・目的: 必須 column 不足を destructive でない差分として検出できることを守る。
# テストケース: copilot_sessions.summary_payload を actual metadata から除外する。
# 期待値: missing に不足列が入り、compatible false になる。
def test_compare_metadata_reports_missing_columns_as_incompatible_state() -> None:
    columns = _without_column(
        _expected_columns(),
        table_name="dev_copilot_sessions",
        column_name="summary_payload",
    )

    diff = compare_metadata(
        expected=read_model_tables(table_prefix="dev_"),
        actual_columns=columns,
        actual_options=_expected_options(),
    )

    assert diff.compatible is False
    assert diff.missing == ("dev_copilot_sessions.summary_payload",)
    assert diff.incompatible == ()


# 概要・目的: 型や nullability の差分を schema 契約違反として分類できることを守る。
# テストケース: history_sync_runs.saved_count の type と mode を actual metadata で変える。
# 期待値: incompatible に type mismatch と mode mismatch が決定的に入る。
def test_compare_metadata_reports_type_and_mode_mismatches() -> None:
    columns = _expected_columns()
    for row in columns:
        if row["table_name"] == "dev_history_sync_runs" and row["column_name"] == "saved_count":
            row["data_type"] = "STRING"
            row["is_nullable"] = "YES"

    diff = compare_metadata(
        expected=read_model_tables(table_prefix="dev_"),
        actual_columns=columns,
        actual_options=_expected_options(),
    )

    assert diff.compatible is False
    assert diff.incompatible == (
        "dev_history_sync_runs.saved_count type expected INT64 but was STRING",
        "dev_history_sync_runs.saved_count mode expected REQUIRED but was NULLABLE",
    )


# 概要・目的: partition / clustering layout の差分を compare mode で失敗扱いにできることを守る。
# テストケース: partition column marker と clustering order と require_partition_filter を変える。
# 期待値: incompatible に layout 差分が入り、compatible false になる。
def test_compare_metadata_reports_partition_clustering_and_option_mismatches() -> None:
    columns = _expected_columns()
    options = _expected_options()
    for row in columns:
        if row["table_name"] == "dev_copilot_sessions":
            if row["column_name"] == "source_partition_date":
                row["is_partitioning_column"] = "NO"
            if row["column_name"] == "repository":
                row["clustering_ordinal_position"] = 1
            if row["column_name"] == "session_id":
                row["clustering_ordinal_position"] = 2
    for row in options:
        if row["table_name"] == "dev_copilot_sessions":
            row["option_value"] = "false"

    diff = compare_metadata(
        expected=read_model_tables(table_prefix="dev_"),
        actual_columns=columns,
        actual_options=options,
    )

    assert diff.compatible is False
    assert diff.incompatible == (
        "dev_copilot_sessions partition expected source_partition_date but was absent",
        "dev_copilot_sessions clustering expected "
        "('session_id', 'repository', 'branch', 'source_format') but was "
        "('repository', 'session_id', 'branch', 'source_format')",
        "dev_copilot_sessions option require_partition_filter expected true but was false",
    )


# 概要・目的: schema 契約にない余分な列を自動削除せず informational に留めることを守る。
# テストケース: actual metadata に dev_copilot_sessions.extra_debug_column を追加する。
# 期待値: extra に分類されるが compatible は true のままになる。
def test_compare_metadata_reports_extra_columns_as_informational() -> None:
    columns: list[Mapping[str, object]] = [
        *_expected_columns(),
        {
            "table_name": "dev_copilot_sessions",
            "column_name": "extra_debug_column",
            "data_type": "STRING",
            "is_nullable": "YES",
            "is_partitioning_column": "NO",
            "clustering_ordinal_position": None,
        },
    ]

    diff = compare_metadata(
        expected=read_model_tables(table_prefix="dev_"),
        actual_columns=columns,
        actual_options=_expected_options(),
    )

    assert diff.compatible is True
    assert diff.extra == ("dev_copilot_sessions.extra_debug_column",)

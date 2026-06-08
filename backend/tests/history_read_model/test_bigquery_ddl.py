from history_read_model.bigquery_schema import table_by_base_name
from history_read_model.bigquery_settings import BigQueryReadModelSettings
from history_read_model.ddl import (
    build_create_dataset_sql,
    build_create_table_sql,
    build_schema_metadata_sql,
)


def _settings() -> BigQueryReadModelSettings:
    return BigQueryReadModelSettings(
        project_id="local-project",
        dataset_id="copilot_history",
        location="asia-northeast1",
        table_prefix="dev_",
        credentials_path=None,
    )


# 概要・目的: dataset 作成 SQL が dry-run 表示できる決定的な契約を守る。
# テストケース: 検証済み settings から CREATE SCHEMA SQL を生成する。
# 期待値: project / dataset / location が quoted identifier と option として反映される。
def test_build_create_dataset_sql_includes_target_dataset_and_location() -> None:
    sql = build_create_dataset_sql(_settings())

    assert sql == (
        "CREATE SCHEMA IF NOT EXISTS `local-project.copilot_history`\n"
        "OPTIONS(location = 'asia-northeast1');"
    )


# 概要・目的: copilot_sessions の physical layout が DDL に反映されることを守る。
# テストケース: prefix 付き copilot_sessions table から CREATE TABLE SQL を生成する。
# 期待値: JSON columns、partition、require_partition_filter、clustering が含まれる。
def test_build_create_table_sql_for_copilot_sessions_includes_schema_and_layout() -> None:
    table = table_by_base_name("copilot_sessions", table_prefix="dev_")
    sql = build_create_table_sql(_settings(), table)

    assert "CREATE TABLE IF NOT EXISTS `local-project.copilot_history.dev_copilot_sessions`" in sql
    assert "`session_id` STRING NOT NULL" in sql
    assert "`summary_payload` JSON NOT NULL" in sql
    assert "`detail_payload` JSON NOT NULL" in sql
    assert "PARTITION BY source_partition_date" in sql
    assert "CLUSTER BY session_id, repository, branch, source_format" in sql
    assert "OPTIONS(require_partition_filter = TRUE);" in sql


# 概要・目的: history_sync_runs の started_at 由来 layout が DDL に反映されることを守る。
# テストケース: prefix 付き history_sync_runs table から CREATE TABLE SQL を生成する。
# 期待値: sync lifecycle columns、partition、clustering、partition filter option が含まれる。
def test_build_create_table_sql_for_history_sync_runs_includes_schema_and_layout() -> None:
    table = table_by_base_name("history_sync_runs", table_prefix="dev_")
    sql = build_create_table_sql(_settings(), table)

    assert "CREATE TABLE IF NOT EXISTS `local-project.copilot_history.dev_history_sync_runs`" in sql
    assert "`status` STRING NOT NULL" in sql
    assert "`started_partition_date` DATE NOT NULL" in sql
    assert "`running_lock_key` STRING" in sql
    assert "PARTITION BY started_partition_date" in sql
    assert "CLUSTER BY status, started_at, running_lock_key" in sql
    assert "OPTIONS(require_partition_filter = FALSE);" in sql


# 概要・目的: compare mode が schema / option metadata を取得する SQL 契約を守る。
# テストケース: settings から metadata comparison 用 SQL を生成する。
# 期待値: COLUMNS と TABLE_OPTIONS の両方を参照し、対象 table names に限定される。
def test_build_schema_metadata_sql_includes_columns_and_table_options_queries() -> None:
    sql = build_schema_metadata_sql(_settings())

    assert "`local-project.copilot_history.INFORMATION_SCHEMA.COLUMNS`" in sql
    assert "`local-project.copilot_history.INFORMATION_SCHEMA.TABLE_OPTIONS`" in sql
    assert "'dev_copilot_sessions'" in sql
    assert "'dev_history_sync_runs'" in sql
    assert "clustering_ordinal_position" in sql
    assert "option_name" in sql

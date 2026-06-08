from history_read_model.bigquery_schema import (
    COPILOT_SESSION_COUNT_FIELDS,
    HISTORY_SYNC_RUN_COUNT_FIELDS,
    SOURCE_FORMAT_VALUES,
    SOURCE_STATE_VALUES,
    SYNC_STATUS_VALUES,
    table_by_base_name,
)


# 概要・目的: copilot_sessions が後続 repository の保存先として必要な列契約を持つことを守る。
# テストケース: prefix なしの copilot_sessions schema から列名、型、必須性、既定値相当を読む。
# 期待値: identity、source metadata、counts、payload、search の主要列が契約通り定義される。
def test_copilot_sessions_schema_defines_required_read_model_columns() -> None:
    table = table_by_base_name("copilot_sessions")
    columns = table.column_map

    assert table.name == "copilot_sessions"
    assert columns["session_id"].type == "STRING"
    assert columns["session_id"].mode == "REQUIRED"
    assert columns["source_format"].allowed_values == SOURCE_FORMAT_VALUES
    assert columns["source_state"].allowed_values == SOURCE_STATE_VALUES
    assert columns["created_at_source"].type == "TIMESTAMP"
    assert columns["updated_at_source"].type == "TIMESTAMP"
    assert columns["repository"].mode == "NULLABLE"
    assert columns["branch"].mode == "NULLABLE"
    assert columns["degraded"].type == "BOOL"
    assert columns["degraded"].default_equivalent is False
    assert columns["conversation_preview"].type == "STRING"
    assert columns["source_paths"].type == "JSON"
    assert columns["source_fingerprint"].type == "JSON"
    assert columns["summary_payload"].type == "JSON"
    assert columns["summary_payload"].json_object is True
    assert columns["detail_payload"].type == "JSON"
    assert columns["detail_payload"].json_object is True
    assert columns["search_text"].type == "STRING"
    assert columns["search_text"].default_equivalent == ""
    assert columns["search_text_version"].default_equivalent == 0
    assert columns["indexed_at"].type == "TIMESTAMP"
    assert table.read_model_role == "regenerable_from_raw_files"


# 概要・目的: copilot_sessions の count fields が非負整数として検証可能な契約を守る。
# テストケース: schema が公開する count field 一覧と各列属性を照合する。
# 期待値: Rails と同じ count fields が INT64 REQUIRED、default equivalent 0、非負になる。
def test_copilot_sessions_count_fields_are_non_negative_int64_columns() -> None:
    table = table_by_base_name("copilot_sessions")
    columns = table.column_map

    assert COPILOT_SESSION_COUNT_FIELDS == (
        "event_count",
        "message_snapshot_count",
        "issue_count",
        "message_count",
        "activity_count",
    )
    for field_name in COPILOT_SESSION_COUNT_FIELDS:
        assert columns[field_name].type == "INT64"
        assert columns[field_name].mode == "REQUIRED"
        assert columns[field_name].default_equivalent == 0
        assert columns[field_name].non_negative is True


# 概要・目的: history_sync_runs が同期 lifecycle と実行集計の保存契約を持つことを守る。
# テストケース: history_sync_runs schema から status、timestamp、count、summary、lock 列を読む。
# 期待値: lifecycle invariant と saved count invariant を追跡できる列契約が定義される。
def test_history_sync_runs_schema_defines_lifecycle_and_count_contract() -> None:
    table = table_by_base_name("history_sync_runs")
    columns = table.column_map

    assert table.name == "history_sync_runs"
    assert columns["status"].type == "STRING"
    assert columns["status"].mode == "REQUIRED"
    assert columns["status"].allowed_values == SYNC_STATUS_VALUES
    assert table.running_status == "running"
    assert table.terminal_statuses == ("succeeded", "failed", "completed_with_issues")
    assert table.saved_count_equals == ("inserted_count", "updated_count")
    assert columns["started_at"].type == "TIMESTAMP"
    assert columns["started_at"].mode == "REQUIRED"
    assert columns["finished_at"].type == "TIMESTAMP"
    assert columns["finished_at"].mode == "NULLABLE"
    assert columns["failure_summary"].type == "STRING"
    assert columns["degradation_summary"].type == "STRING"
    assert columns["running_lock_key"].type == "STRING"
    assert columns["running_lock_key"].mode == "NULLABLE"

    for field_name in HISTORY_SYNC_RUN_COUNT_FIELDS:
        assert columns[field_name].type == "INT64"
        assert columns[field_name].mode == "REQUIRED"
        assert columns[field_name].default_equivalent == 0
        assert columns[field_name].non_negative is True


# 概要・目的: partition / clustering と table prefix が後続 query 前提として追跡できることを守る。
# テストケース: prefix 付き schema から両 table の physical layout を読む。
# 期待値: date range、session lookup、repository / branch、sync status 用の layout が定義される。
def test_partition_clustering_and_prefixed_table_names_are_contractual() -> None:
    sessions_table = table_by_base_name("copilot_sessions", table_prefix="dev_")
    sync_runs_table = table_by_base_name("history_sync_runs", table_prefix="dev_")

    assert sessions_table.name == "dev_copilot_sessions"
    assert sessions_table.partition_by == "source_partition_date"
    assert sessions_table.partition_source == "updated_at_source"
    assert sessions_table.require_partition_filter is True
    assert sessions_table.cluster_by == (
        "session_id",
        "repository",
        "branch",
        "source_format",
    )
    assert sessions_table.lookup_fields == (
        "source_partition_date",
        "session_id",
        "repository",
        "branch",
        "source_format",
        "source_state",
        "search_text",
    )

    assert sync_runs_table.name == "dev_history_sync_runs"
    assert sync_runs_table.partition_by == "started_partition_date"
    assert sync_runs_table.partition_source == "started_at"
    assert sync_runs_table.require_partition_filter is False
    assert sync_runs_table.cluster_by == ("status", "started_at", "running_lock_key")
    assert sync_runs_table.lookup_fields == ("started_at", "status", "running_lock_key")
    assert sync_runs_table.cost_optimization_scope == "initial_layout_only"

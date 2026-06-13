from datetime import UTC, date, datetime

from history_read_model.bigquery_sql import (
    build_running_sync_run_query,
    build_session_detail_query,
    build_session_list_query,
    build_session_merge_query,
    build_session_metadata_query,
    build_sync_run_upsert_query,
)
from history_read_model.fake_repository import HistorySyncRunRow
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


def _criteria() -> SessionListCriteria:
    return SessionListCriteria(
        from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
        to_datetime=datetime(2026, 6, 9, tzinfo=UTC),
        search_term="BigQuery%' OR 1=1 --",
        limit=20,
    )


# 概要・目的: BigQuery list SQL が partition predicate と display time 条件を必ず含むことを守る。
# テストケース: date range / search / limit を含む criteria から list query を生成する。
# 期待値: source_partition_date と COALESCE(updated_at_source, created_at_source) が条件に含まれる。
def test_build_session_list_query_includes_partition_and_display_time_filters() -> None:
    query = build_session_list_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        criteria=_criteria(),
        options=RepositoryExecutionOptions(maximum_bytes_billed=1024),
    )

    assert "`local-project.history_dataset.dev_copilot_sessions`" in query.sql
    assert "source_partition_date BETWEEN @from_date AND @to_date" in query.sql
    assert "COALESCE(updated_at_source, created_at_source)" in query.sql
    assert "display_time BETWEEN @from_datetime AND @to_datetime" in query.sql
    assert "display_time IS NOT NULL" in query.sql
    assert query.maximum_bytes_billed == 1024


# 概要・目的: BigQuery list SQL が同一 SELECT の WHERE で SELECT alias を参照しないことを守る。
# テストケース: display_time alias を使う list query の CTE 構造を確認する。
# 期待値: display_time は source_rows で算出され、
# 候補絞り込みは外側 CTE の FROM source_rows 後に行われる。
def test_build_session_list_query_filters_display_time_after_alias_projection() -> None:
    query = build_session_list_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="",
        criteria=_criteria(),
        options=RepositoryExecutionOptions(),
    )

    assert "WITH source_rows AS (" in query.sql
    assert "FROM source_rows" in query.sql
    source_rows_body = query.sql.split("),\ncandidates AS", maxsplit=1)[0]
    assert "display_time BETWEEN" not in source_rows_body


# 概要・目的: BigQuery list SQL が user input を直埋めせず named parameters で扱う。
# テストケース: SQL 注入風の検索語を criteria に入れて query を生成する。
# 期待値: SQL 本文に検索語は現れず、search_term / limit などが named parameter として保持される。
def test_build_session_list_query_uses_named_parameters_for_user_input() -> None:
    query = build_session_list_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="",
        criteria=_criteria(),
        options=RepositoryExecutionOptions(),
    )

    assert "OR 1=1" not in query.sql
    assert query.parameter_value("search_term") == "%bigquery%' or 1=1 --%"
    assert query.parameter_value("limit") == 20
    assert query.parameter_value("from_datetime") == datetime(2026, 6, 1, tzinfo=UTC)
    assert query.parameter_value("to_datetime") == datetime(2026, 6, 9, tzinfo=UTC)


# 概要・目的: BigQuery list SQL が検索対象を search_text と cwd に限定することを守る。
# テストケース: search_term を含む criteria で query を生成する。
# 期待値: search_text / cwd の LIKE 条件だけが追加され、repository metadata は検索対象にならない。
def test_build_session_list_query_searches_only_saved_search_text_and_cwd() -> None:
    query = build_session_list_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="",
        criteria=_criteria(),
        options=RepositoryExecutionOptions(),
    )

    assert "LOWER(search_text) LIKE @search_term" in query.sql
    assert "LOWER(COALESCE(cwd, '')) LIKE @search_term" in query.sql
    assert "LOWER(repository)" not in query.sql
    assert "LOWER(branch)" not in query.sql


# 概要・目的: BigQuery list SQL が安定 ordering と limit を BigQuery 側に表現することを守る。
# テストケース: limit 付き criteria で query を生成する。
# 期待値: display_time DESC、session_id ASC の順序と named parameter limit が SQL に含まれる。
def test_build_session_list_query_orders_stably_and_limits_after_ordering() -> None:
    query = build_session_list_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="",
        criteria=_criteria(),
        options=RepositoryExecutionOptions(),
    )

    assert "ORDER BY display_time DESC, session_id ASC" in query.sql
    assert query.sql.rstrip().endswith("LIMIT @limit")


# 概要・目的: BigQuery detail SQL が raw files を読まず保存済み payload lookup に閉じることを守る。
# テストケース: session_id を指定して detail query を生成する。
# 期待値: detail_payload を session_id named parameter と partition filter で取得する。
def test_build_session_detail_query_uses_session_id_named_parameter() -> None:
    query = build_session_detail_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        session_id="session-1",
        options=RepositoryExecutionOptions(maximum_bytes_billed=2048, dry_run=True),
    )

    assert "`local-project.history_dataset.dev_copilot_sessions`" in query.sql
    assert "SELECT detail_payload" in query.sql
    assert "WHERE session_id = @session_id" in query.sql
    assert "source_partition_date BETWEEN DATE '1970-01-01' AND CURRENT_DATE()" in query.sql
    assert "session-1" not in query.sql
    assert query.parameter_value("session_id") == "session-1"
    assert query.dry_run is True
    assert query.maximum_bytes_billed == 2048


# 概要・目的: BigQuery metadata lookup SQL が保存候補 session ID だけを named parameter で参照する。
# テストケース: 2 件の session_id から metadata lookup query を生成する。
# 期待値: 分類に必要な 3 field だけを SELECT し、session_id array parameter で対象を限定する。
def test_build_session_metadata_query_selects_only_planner_fields_for_candidate_ids() -> None:
    query = build_session_metadata_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        session_ids=("session-1", "session-2"),
        partition_dates=(date(2026, 6, 1), date(2026, 6, 9)),
        options=RepositoryExecutionOptions(maximum_bytes_billed=4096),
    )

    assert "SELECT session_id, source_fingerprint, search_text_version" in query.sql
    assert "summary_payload" not in query.sql
    assert "detail_payload" not in query.sql
    assert "source_partition_date BETWEEN @from_date AND @to_date" in query.sql
    assert "AND session_id IN UNNEST(@session_ids)" in query.sql
    assert query.parameter_value("session_ids") == ("session-1", "session-2")
    assert query.parameter_value("from_date") == date(2026, 6, 1)
    assert query.parameter_value("to_date") == date(2026, 6, 9)
    assert query.maximum_bytes_billed == 4096


# 概要・目的: BigQuery MERGE SQL が session_id identity で重複 row を作らないことを守る。
# テストケース: staging table と対象 session_id から MERGE query を生成する。
# 期待値: target と staging を session_id で結合し、
# insert/update 対象だけを named parameter で限定する。
def test_build_session_merge_query_uses_session_identity_and_candidate_filter() -> None:
    query = build_session_merge_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        staging_table_id="local-project.history_dataset.session_stage_sync_1",
        session_ids=("inserted", "updated"),
        partition_dates=(date(2026, 6, 9),),
        options=RepositoryExecutionOptions(dry_run=True),
    )

    assert "MERGE `local-project.history_dataset.dev_copilot_sessions` AS target" in query.sql
    assert "FROM `local-project.history_dataset.session_stage_sync_1`" in query.sql
    assert "ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY indexed_at DESC) = 1" in query.sql
    assert "ON target.session_id = source.session_id" in query.sql
    assert "target.source_partition_date BETWEEN @from_date AND @to_date" in query.sql
    assert "WHERE session_id IN UNNEST(@session_ids)" in query.sql
    assert "WHEN MATCHED THEN" in query.sql
    assert "WHEN NOT MATCHED THEN" in query.sql
    assert query.parameter_value("session_ids") == ("inserted", "updated")
    assert query.dry_run is True


# 概要・目的: sync run upsert SQL が lifecycle row を history_sync_runs に保存できる構造を守る。
# テストケース: running sync run row から upsert query を生成する。
# 期待値: sync_run_id identity の MERGE で
# status/count/lock field を named parameter として保持する。
def test_build_sync_run_upsert_query_uses_sync_run_identity_and_parameters() -> None:
    started_at = datetime(2026, 6, 9, 10, tzinfo=UTC)
    row = HistorySyncRunRow(
        sync_run_id="sync-1",
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
        running_lock_key="history-sync",
        indexed_at=started_at,
    )

    query = build_sync_run_upsert_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        row=row,
        options=RepositoryExecutionOptions(),
    )

    assert "MERGE `local-project.history_dataset.dev_history_sync_runs` AS target" in query.sql
    assert "ON target.sync_run_id = source.sync_run_id" in query.sql
    assert query.parameter_value("sync_run_id") == "sync-1"
    assert query.parameter_value("status") == "running"
    assert query.parameter_value("running_lock_key") == "history-sync"


# 概要・目的: running sync lookup SQL が未完了 run だけを識別する契約を守る。
# テストケース: running lookup query を生成する。
# 期待値: status running と running_lock_key の存在で絞り、sync_run_id だけを返す。
def test_build_running_sync_run_query_filters_running_lock_rows() -> None:
    query = build_running_sync_run_query(
        project_id="local-project",
        dataset_id="history_dataset",
        table_prefix="dev_",
        options=RepositoryExecutionOptions(dry_run=True),
    )

    assert "SELECT sync_run_id" in query.sql
    assert "FROM `local-project.history_dataset.dev_history_sync_runs`" in query.sql
    assert "status = @running_status" in query.sql
    assert "running_lock_key IS NOT NULL" in query.sql
    assert query.parameter_value("running_status") == "running"
    assert query.dry_run is True

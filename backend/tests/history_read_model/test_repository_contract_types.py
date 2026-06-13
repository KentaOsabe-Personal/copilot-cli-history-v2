from datetime import UTC, datetime
from typing import cast

import pytest

from history_read_model.repository import (
    RepositoryError,
    RepositoryErrorKind,
    RepositoryExecutionOptions,
    SessionDetailResult,
    SessionListCriteria,
    SessionListResult,
    SyncRunLookupResult,
    SyncRunResult,
    SyncWriteResult,
    validate_repository_options,
    validate_session_id,
    validate_session_list_criteria,
)


# 概要・目的: repository port が一覧条件の明示 date range 必須契約を
# BigQuery 実行前に表現できることを守る。
# テストケース: from_datetime または to_datetime を欠落させた criteria を validation する。
# 期待値: missing_date_range の RepositoryError が返り、BigQuery job を作らず識別できる。
def test_session_list_criteria_requires_explicit_date_range() -> None:
    criteria = SessionListCriteria(
        from_datetime=None,
        to_datetime=datetime(2026, 6, 9, 23, 59, tzinfo=UTC),
    )

    error = validate_session_list_criteria(criteria)

    assert error == RepositoryError(
        kind="missing_date_range",
        message="session list requires from_datetime and to_datetime",
    )


# 概要・目的: repository port が一覧条件の limit と日付順序を実行前 validation で固定する。
# テストケース: from_datetime が to_datetime より後で、limit が 0 の criteria を validation する。
# 期待値: validation_error として複数理由を details に保持し、BigQuery failure と混同しない。
def test_session_list_criteria_rejects_invalid_range_and_limit() -> None:
    criteria = SessionListCriteria(
        from_datetime=datetime(2026, 6, 10, tzinfo=UTC),
        to_datetime=datetime(2026, 6, 9, tzinfo=UTC),
        limit=0,
    )

    error = validate_session_list_criteria(criteria)

    assert error is not None
    assert error.kind == "validation_error"
    assert error.details == {
        "fields": ("from_datetime", "limit"),
        "reasons": (
            "from_datetime must be earlier than or equal to to_datetime",
            "limit must be a positive integer when provided",
        ),
    }


# 概要・目的: detail lookup が空 session ID を repository-local validation error にできる。
# テストケース: 空白だけの session_id を validation する。
# 期待値: validation_error が返り、not found や BigQuery query failure と混同しない。
def test_validate_session_id_rejects_blank_values() -> None:
    error = validate_session_id("  ")

    assert error == RepositoryError(
        kind="validation_error",
        message="session_id must not be blank",
        details={"fields": ("session_id",)},
    )


# 概要・目的: repository execution options が dry run / cost guardrail を表現する。
# テストケース: dry_run と maximum_bytes_billed と location を指定して validation する。
# 期待値: options は BigQuery client を生成せず保持でき、有効な上限は validation error にならない。
def test_repository_execution_options_carry_cost_guardrails_without_client() -> None:
    options = RepositoryExecutionOptions(
        dry_run=True,
        maximum_bytes_billed=1024,
        location="asia-northeast1",
    )

    assert validate_repository_options(options) is None
    assert options.dry_run is True
    assert options.maximum_bytes_billed == 1024
    assert options.location == "asia-northeast1"


# 概要・目的: maximum bytes billed の無効値を BigQuery 実行前に repository error として識別する。
# テストケース: maximum_bytes_billed に 0 を指定して validation する。
# 期待値: validation_error が返り、cost_limit_exceeded など実行後 failure と分離される。
def test_repository_execution_options_reject_invalid_maximum_bytes_billed() -> None:
    error = validate_repository_options(RepositoryExecutionOptions(maximum_bytes_billed=0))

    assert error == RepositoryError(
        kind="validation_error",
        message="maximum_bytes_billed must be a positive integer when provided",
        details={"fields": ("maximum_bytes_billed",)},
    )


# 概要・目的: list result が presenter-compatible summary payload を別 shape に変換せず保持する。
# テストケース: 保存済み summary payload の tuple を success result に入れる。
# 期待値: payload mapping が同一 object として返り、空 result も success として表現できる。
def test_session_list_result_preserves_summary_payload_objects() -> None:
    summary: dict[str, object] = {"id": "session-1", "title": "Saved session"}
    result = SessionListResult.success([summary])
    empty_result = SessionListResult.success([])

    assert result.ok is True
    assert result.summary_payloads == (summary,)
    assert result.summary_payloads[0] is summary
    assert empty_result.ok is True
    assert empty_result.summary_payloads == ()


# 概要・目的: detail result が found / not found / error を同じ契約で識別できることを守る。
# テストケース: found、not_found、error の factory を作る。
# 期待値: found は detail payload を透過保持し、not found は失敗ではなく識別可能な result になる。
def test_session_detail_result_distinguishes_found_not_found_and_error() -> None:
    detail: dict[str, object] = {"conversation": []}
    found = SessionDetailResult.success(detail)
    not_found = SessionDetailResult.not_found("missing-session")
    failed = SessionDetailResult.failure(
        RepositoryError(kind="query_failed", message="query failed")
    )

    assert found.ok is True
    assert found.found is True
    assert found.detail_payload is detail
    assert not_found.ok is True
    assert not_found.found is False
    assert not_found.session_id == "missing-session"
    assert failed.ok is False
    assert failed.error is not None
    assert failed.error.kind == "query_failed"


# 概要・目的: sync write result が session 保存件数と dry-run 実行予定を返せる。
# テストケース: processed / inserted / updated / saved / skipped / failed / degraded を指定する。
# 期待値: saved count は inserted + updated と一致し、dry_run は予定として保持される。
def test_sync_write_result_carries_counts_and_dry_run_plan() -> None:
    result = SyncWriteResult.success(
        processed_count=4,
        inserted_count=1,
        updated_count=2,
        skipped_count=1,
        failed_count=0,
        degraded_count=1,
        dry_run=True,
        planned_operations=("metadata_lookup", "merge"),
    )

    assert result.ok is True
    assert result.saved_count == 3
    assert result.processed_count == 4
    assert result.degraded_count == 1
    assert result.dry_run is True
    assert result.planned_operations == ("metadata_lookup", "merge")


# 概要・目的: sync run result が lifecycle 保存と running lock lookup の port 契約を表現する。
# テストケース: sync run 保存 success と running lookup found / not found を作る。
# 期待値: BigQuery table details なしで sync_run_id と running lock の有無を識別できる。
def test_sync_run_results_express_save_and_running_lookup_contract() -> None:
    saved = SyncRunResult.success(sync_run_id="sync-1")
    running = SyncRunLookupResult.success(sync_run_id="sync-1")
    not_running = SyncRunLookupResult.not_found()

    assert saved.ok is True
    assert saved.sync_run_id == "sync-1"
    assert running.ok is True
    assert running.found is True
    assert running.sync_run_id == "sync-1"
    assert not_running.ok is True
    assert not_running.found is False
    assert not_running.sync_run_id is None


# 概要・目的: repository error kind が設計された失敗分類だけを許可する型契約を守る。
# テストケース: credentials / permission / schema / cost / query failure の kind を生成する。
# 期待値: すべて RepositoryError として表現でき、呼び出し側が失敗種別で分岐できる。
@pytest.mark.parametrize(
    "kind",
    [
        "credentials_error",
        "permission_denied",
        "schema_mismatch",
        "cost_limit_exceeded",
        "query_failed",
    ],
)
def test_repository_error_kind_covers_bigquery_failure_classes(kind: str) -> None:
    error = RepositoryError(kind=cast(RepositoryErrorKind, kind), message="failed")

    assert error.kind == kind

from datetime import UTC, datetime
from typing import Any, cast

from copilot_history.api.presenters import ErrorPresenter, HistorySyncPresenter
from copilot_history.api.types import (
    HistorySyncCountsPresentationInput,
    HistorySyncPresentationResult,
    HistorySyncRunPresentationInput,
    RootFailurePresentationInput,
    ValidationErrorPresentationInput,
)

STARTED_AT = datetime(2026, 4, 30, 8, 55, tzinfo=UTC)
FINISHED_AT = datetime(2026, 4, 30, 8, 55, 1, tzinfo=UTC)


def _run(
    *,
    run_id: int = 101,
    status: str = "succeeded",
    started_at: datetime | None = STARTED_AT,
    finished_at: datetime | None = FINISHED_AT,
) -> HistorySyncRunPresentationInput:
    return HistorySyncRunPresentationInput(
        id=run_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
    )


def _counts(
    *, degraded_count: int = 0, failed_count: int = 0
) -> HistorySyncCountsPresentationInput:
    return HistorySyncCountsPresentationInput(
        processed_count=2 if failed_count == 0 else 0,
        inserted_count=2 if failed_count == 0 else 0,
        updated_count=0,
        saved_count=2 if failed_count == 0 else 0,
        skipped_count=0,
        failed_count=failed_count,
        degraded_count=degraded_count,
    )


# 概要・目的: history sync success Presenter が error envelope を混ぜない契約を守る。
# テストケース: succeeded と completed_with_issues の sync result を response body にする。
# 期待値: data.sync_run と data.counts の success envelope だけが返り、degraded_count が保持される。
def test_history_sync_presenter_returns_success_body_for_successful_kinds() -> None:
    presenter = HistorySyncPresenter()

    succeeded = presenter.present(
        HistorySyncPresentationResult(kind="succeeded", sync_run=_run(), counts=_counts())
    )
    completed_with_issues = presenter.present(
        HistorySyncPresentationResult(
            kind="completed_with_issues",
            sync_run=_run(
                run_id=102,
                status="completed_with_issues",
                started_at=datetime(2026, 4, 30, 8, 56, tzinfo=UTC),
                finished_at=datetime(2026, 4, 30, 8, 56, 2, tzinfo=UTC),
            ),
            counts=_counts(degraded_count=1),
        )
    )

    assert succeeded == {
        "data": {
            "sync_run": {
                "id": 101,
                "status": "succeeded",
                "started_at": "2026-04-30T08:55:00Z",
                "finished_at": "2026-04-30T08:55:01Z",
            },
            "counts": {
                "processed_count": 2,
                "inserted_count": 2,
                "updated_count": 0,
                "saved_count": 2,
                "skipped_count": 0,
                "failed_count": 0,
                "degraded_count": 0,
            },
        }
    }
    completed_data = cast(dict[str, Any], completed_with_issues["data"])
    completed_run = cast(dict[str, Any], completed_data["sync_run"])
    completed_counts = cast(dict[str, Any], completed_data["counts"])
    assert completed_run["status"] == "completed_with_issues"
    assert completed_counts["degraded_count"] == 1
    assert "error" not in completed_with_issues


# 概要・目的: history sync running conflict が専用 error envelope になる契約を守る。
# テストケース: running run を conflict result として response body にする。
# 期待値: history_sync_running code と running run の id / started_at が details に返る。
def test_history_sync_presenter_returns_running_conflict_error_body() -> None:
    body = HistorySyncPresenter().present(
        HistorySyncPresentationResult(
            kind="conflict",
            sync_run=_run(
                run_id=100,
                status="running",
                started_at=STARTED_AT,
                finished_at=None,
            ),
        )
    )

    assert body == {
        "error": {
            "code": "history_sync_running",
            "message": "history sync is already running",
            "details": {
                "sync_run_id": 100,
                "started_at": "2026-04-30T08:55:00Z",
            },
        }
    }


# 概要・目的: history sync failure Presenter が fixture と同じ error body と meta を返す契約を守る。
# テストケース: root failure と persistence failure の sync result を response body にする。
# 期待値: error details、meta.sync_run、meta.counts が保持され、data envelope は混在しない。
def test_history_sync_presenter_returns_failure_error_body_with_meta() -> None:
    presenter = HistorySyncPresenter()

    root_failure = presenter.present(
        HistorySyncPresentationResult(
            kind="root_failure",
            sync_run=_run(
                run_id=103,
                status="failed",
                started_at=datetime(2026, 4, 30, 8, 57, tzinfo=UTC),
                finished_at=datetime(2026, 4, 30, 8, 57, 1, tzinfo=UTC),
            ),
            counts=_counts(failed_count=1),
            error_code="root_missing",
            error_message="history root does not exist",
            error_details={"path": "/tmp/copilot-missing-home/.copilot"},
        )
    )
    persistence_failure = presenter.present(
        HistorySyncPresentationResult(
            kind="persistence_failure",
            sync_run=_run(
                run_id=104,
                status="failed",
                started_at=datetime(2026, 4, 30, 8, 58, tzinfo=UTC),
                finished_at=datetime(2026, 4, 30, 8, 58, 1, tzinfo=UTC),
            ),
            counts=_counts(failed_count=1),
            error_code="history_sync_failed",
            error_message="history sync failed",
            error_details={
                "failure_class": "ActiveRecord::RecordInvalid",
                "sync_run_id": 104,
            },
        )
    )

    assert root_failure["error"] == {
        "code": "root_missing",
        "message": "history root does not exist",
        "details": {"path": "/tmp/copilot-missing-home/.copilot"},
    }
    root_meta = cast(dict[str, Any], root_failure["meta"])
    root_meta_run = cast(dict[str, Any], root_meta["sync_run"])
    root_meta_counts = cast(dict[str, Any], root_meta["counts"])
    persistence_error = cast(dict[str, Any], persistence_failure["error"])
    persistence_meta = cast(dict[str, Any], persistence_failure["meta"])
    persistence_meta_run = cast(dict[str, Any], persistence_meta["sync_run"])
    assert root_meta_run["id"] == 103
    assert root_meta_counts["failed_count"] == 1
    assert persistence_error["code"] == "history_sync_failed"
    assert persistence_meta_run["finished_at"] == "2026-04-30T08:58:01Z"
    assert "data" not in root_failure


# 概要・目的: common error Presenter が success envelope を混ぜない契約を守る。
# テストケース: session not found、validation error、root failure input を response body にする。
# 期待値: top-level error のみが返り、details key は upstream 入力の名前を保持する。
def test_error_presenter_returns_common_error_envelopes() -> None:
    presenter = ErrorPresenter()

    not_found = presenter.from_not_found(session_id="missing-session")
    validation = presenter.from_validation(
        ValidationErrorPresentationInput(
            code="invalid_session_list_query",
            message="session list query is invalid",
            details={"field": "range", "reason": "from_after_to"},
        )
    )
    root_failure = presenter.from_root_failure(
        RootFailurePresentationInput(
            code="root_missing",
            message="history root does not exist",
            path="/tmp/copilot-missing-home/.copilot",
        )
    )

    assert not_found == {
        "error": {
            "code": "session_not_found",
            "message": "session was not found",
            "details": {"session_id": "missing-session"},
        }
    }
    assert validation == {
        "error": {
            "code": "invalid_session_list_query",
            "message": "session list query is invalid",
            "details": {"field": "range", "reason": "from_after_to"},
        }
    }
    assert root_failure == {
        "error": {
            "code": "root_missing",
            "message": "history root does not exist",
            "details": {"path": "/tmp/copilot-missing-home/.copilot"},
        }
    }
    assert set(not_found) == {"error"}

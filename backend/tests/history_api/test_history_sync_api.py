from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn

from django.test import Client

from history_api.dependencies import dependency_overrides
from tests.history_api.fakes import (
    FakeSyncReader,
    build_history_api_test_repository,
    degraded_issue,
    normalized_session,
    sync_reader_root_failure,
    sync_reader_success,
)


class _UnexpectedReader:
    def read(self) -> NoReturn:
        raise AssertionError("sync conflict must not read history files")


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 9, 12, tzinfo=UTC)


# 概要・目的: 同期 API が request 内で同期を完了し成功 response を返す契約を守る。
# テストケース: fake reader が complete session を返す状態で POST /api/history/sync を呼ぶ。
# 期待値: HTTP 200、sync_run と counts が返り、reader は 1 回だけ呼ばれる。
def test_history_sync_api_returns_success_response_in_request() -> None:
    reader = FakeSyncReader(sync_reader_success(normalized_session("synced-session")))

    with dependency_overrides(
        repository=build_history_api_test_repository(),
        reader=reader,
        clock=_fixed_clock,
    ):
        response = Client().post("/api/history/sync")

    assert response.status_code == 200
    assert reader.calls == ["read"]
    assert response.json() == {
        "data": {
            "sync_run": {
                "id": 1781006400000000,
                "status": "succeeded",
                "started_at": "2026-06-09T12:00:00Z",
                "finished_at": "2026-06-09T12:00:00Z",
            },
            "counts": {
                "processed_count": 1,
                "inserted_count": 1,
                "updated_count": 0,
                "saved_count": 1,
                "skipped_count": 0,
                "failed_count": 0,
                "degraded_count": 0,
            },
        }
    }


# 概要・目的: 同期 API が degraded session を error ではなく部分劣化成功として返す。
# テストケース: warning issue 付き degraded session を fake reader から返す。
# 期待値: HTTP 200、sync_run.status は completed_with_issues、degraded_count は 1 になる。
def test_history_sync_api_returns_completed_with_issues_for_degraded_session() -> None:
    reader = FakeSyncReader(
        sync_reader_success(
            normalized_session(
                "degraded-sync-session",
                source_state="degraded",
                issues=(degraded_issue(),),
            )
        )
    )

    with dependency_overrides(
        repository=build_history_api_test_repository(),
        reader=reader,
        clock=_fixed_clock,
    ):
        response = Client().post("/api/history/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["sync_run"]["status"] == "completed_with_issues"
    assert body["data"]["counts"]["degraded_count"] == 1
    assert "error" not in body


# 概要・目的: running conflict 時に reader と session 保存を実行しない契約を守る。
# テストケース: running sync を持つ fake repository と読まれてはいけない reader で同期する。
# 期待値: HTTP 409、sync_run_id/started_at details、既存 session rows の件数維持が観測できる。
def test_history_sync_api_returns_conflict_without_reader_or_session_save() -> None:
    repository = build_history_api_test_repository(sync_state="running")
    before_rows = repository.list_session_rows()

    with dependency_overrides(
        repository=repository,
        reader=_UnexpectedReader(),
        clock=_fixed_clock,
    ):
        response = Client().post("/api/history/sync")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "history_sync_running",
            "message": "history sync is already running",
            "details": {
                "sync_run_id": "sync-running",
                "started_at": "2026-06-09T10:00:00Z",
            },
        }
    }
    assert repository.list_session_rows() == before_rows


# 概要・目的: 履歴 root failure が空成功ではなく error response になる契約を守る。
# テストケース: fake reader が root_missing を返す状態で POST /api/history/sync を呼ぶ。
# 期待値: HTTP 503、root_missing error と failed sync_run meta が返る。
def test_history_sync_api_returns_root_failure_error() -> None:
    reader = FakeSyncReader(sync_reader_root_failure())

    with dependency_overrides(
        repository=build_history_api_test_repository(),
        reader=reader,
        clock=_fixed_clock,
    ):
        response = Client().post("/api/history/sync")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "root_missing",
        "message": "history root does not exist",
        "details": {"path": "/tmp/copilot-missing-home/.copilot"},
    }
    assert response.json()["meta"]["sync_run"]["status"] == "failed"
    assert response.json()["meta"]["counts"]["failed_count"] == 1


# 概要・目的: session 保存失敗が history_sync_failed と sync run meta 付きで返る。
# テストケース: save_sessions が失敗する fake repository で POST /api/history/sync を呼ぶ。
# 期待値: HTTP 500、history_sync_failed details、failed sync_run meta が返る。
def test_history_sync_api_returns_save_failure_error() -> None:
    reader = FakeSyncReader(sync_reader_success(normalized_session("session-1")))

    with dependency_overrides(
        repository=build_history_api_test_repository(sync_state="save_failure"),
        reader=reader,
        clock=_fixed_clock,
    ):
        response = Client().post("/api/history/sync")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "history_sync_failed",
        "message": "history sync failed",
        "details": {
            "kind": "query_failed",
            "mode": "save_failure",
            "sync_run_id": 1781006400000000,
        },
    }
    assert response.json()["meta"]["sync_run"]["status"] == "failed"

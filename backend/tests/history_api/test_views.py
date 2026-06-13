from __future__ import annotations

from typing import NoReturn

from django.test import Client

from history_api.dependencies import dependency_overrides, get_reader
from tests.history_api.fakes import build_history_api_test_repository


class _UnexpectedReader:
    def read(self) -> NoReturn:
        raise AssertionError("sync conflict must not read history files")


def _valid_list_query() -> str:
    return "from=2026-06-09T00:00:00Z&to=2026-06-10T00:00:00Z"


# 概要・目的: 一覧 view が validation、service、response、CORS を接続する契約を守る。
# テストケース: fake repository を dependency override し、許可 origin から一覧 API を呼ぶ。
# 期待値: HTTP 200、summary data/meta、許可 origin の CORS header が返る。
def test_session_list_view_returns_service_response_with_cors() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(
            f"/api/sessions?{_valid_list_query()}",
            headers={"origin": "http://localhost:51730"},
        )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:51730"
    assert response.json()["meta"] == {"count": 2, "partial_results": True}
    assert [session["id"] for session in response.json()["data"]] == [
        "complete-session",
        "degraded-session",
    ]


# 概要・目的: 詳細 view が raw opt-in query と service result を JsonResponse に変換する。
# テストケース: include_raw=true 付きで保存済み complete session の詳細 API を呼ぶ。
# 期待値: HTTP 200、raw_included true、保存済み raw_payload が response に含まれる。
def test_session_detail_view_returns_raw_opt_in_service_response() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions/complete-session?include_raw=true")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["raw_included"] is True
    assert body["data"]["message_snapshots"][0]["raw_payload"] == {
        "type": "assistant.message",
        "content": "complete answer",
    }


# 概要・目的: 詳細 view が not found service result を error envelope と HTTP status に変換する。
# テストケース: fake repository に存在しない session ID の詳細 API を呼ぶ。
# 期待値: HTTP 404 と session_not_found error details が返る。
def test_session_detail_view_returns_not_found_error_response() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions/missing-session")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_not_found",
            "message": "session was not found",
            "details": {"session_id": "missing-session"},
        }
    }


# 概要・目的: 同期 view が service conflict を HTTP 409 error response として返す契約を守る。
# テストケース: running sync を持つ fake repository と読まれてはいけない reader で同期 API を呼ぶ。
# 期待値: HTTP 409、history_sync_running error、reader 未実行のまま response が返る。
def test_history_sync_view_returns_running_conflict_without_reader_side_effect() -> None:
    with dependency_overrides(
        repository=build_history_api_test_repository(sync_state="running"),
        reader=_UnexpectedReader(),
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


# 概要・目的: runtime dependency が通常起動時に reader を遅延生成できる契約を守る。
# テストケース: override なしで get_reader を呼び出す。
# 期待値: SessionCatalogReader 互換の read method を持つ object が返る。
def test_history_api_default_reader_is_created_lazily() -> None:
    reader = get_reader()

    assert reader.__class__.__name__ == "SessionCatalogReader"
    assert callable(reader.read)

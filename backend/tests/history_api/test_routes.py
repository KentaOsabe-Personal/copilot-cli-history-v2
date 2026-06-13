from django.test import Client
from django.urls import resolve

from history_api.dependencies import dependency_overrides
from tests.history_api.fakes import build_history_api_test_repository


# 概要・目的: Django root URLconf が履歴 API の対象 URL を登録する契約を守る。
# テストケース: sync、sessions list、sessions detail の path を URL resolver で解決する。
# 期待値: すべて history_api.views の対応 view へ解決される。
def test_history_api_routes_are_registered() -> None:
    expectations = {
        "/api/history/sync": "history_sync",
        "/api/sessions": "session_list",
        "/api/sessions/complete-session": "session_detail",
    }

    for path, view_name in expectations.items():
        match = resolve(path)

        assert match.func.__module__ == "history_api.views"
        assert match.func.__name__ == view_name


# 概要・目的: 対象 endpoint の許可 method が URL 契約どおりに制限されることを守る。
# テストケース: list/detail へ POST、sync へ GET を送信する。
# 期待値: 許可外 method は成功扱いにならず HTTP 405 を返す。
def test_history_api_rejects_methods_outside_endpoint_contract() -> None:
    client = Client()

    list_response = client.post("/api/sessions")
    detail_response = client.post("/api/sessions/complete-session")
    sync_response = client.get("/api/history/sync")

    assert list_response.status_code == 405
    assert detail_response.status_code == 405
    assert sync_response.status_code == 405


# 概要・目的: preflight request が browser から対象 API を呼べる入口になることを守る。
# テストケース: 許可 origin から list endpoint へ OPTIONS を送る。
# 期待値: HTTP 204 と許可 origin、methods、headers の CORS response が返る。
def test_history_api_options_preflight_returns_cors_headers() -> None:
    response = Client().options(
        "/api/sessions",
        headers={
            "origin": "http://localhost:51730",
            "access-control-request-method": "GET",
            "access-control-request-headers": "content-type",
        },
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:51730"
    assert "GET" in response.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]


# 概要・目的: 対象 endpoint response が許可済み origin にだけ CORS header を返す契約を守る。
# テストケース: allowed origin と disallowed origin から一覧 API を request として呼び分ける。
# 期待値: allowed response だけ Access-Control-Allow-Origin を持ち、wildcard は返らない。
def test_history_api_request_cors_headers_differ_by_origin() -> None:
    query = "from=2026-06-09T00:00:00Z&to=2026-06-10T00:00:00Z"

    with dependency_overrides(repository=build_history_api_test_repository()):
        allowed = Client().get(
            f"/api/sessions?{query}",
            headers={"origin": "http://localhost:51730"},
        )
        disallowed = Client().get(
            f"/api/sessions?{query}",
            headers={"origin": "http://evil.example"},
        )

    assert allowed.status_code == 200
    assert disallowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:51730"
    assert allowed.headers["Access-Control-Allow-Origin"] != "*"
    assert "Access-Control-Allow-Origin" not in disallowed.headers

from typing import Any

from django.http import JsonResponse

from history_api.cors import apply_cors_headers, preflight_response


# 概要・目的: 許可済み development origin だけに CORS header を返す契約を守る。
# テストケース: allowed origin と disallowed origin で response に CORS header を適用する。
# 期待値: allowed origin の response だけ Access-Control-Allow-Origin を持つ。
def test_apply_cors_headers_only_allows_configured_origins(settings: Any) -> None:
    settings.HISTORY_API_ALLOWED_ORIGINS = ("http://localhost:51730",)
    allowed = JsonResponse({"data": []})
    disallowed = JsonResponse({"data": []})

    apply_cors_headers(allowed, origin="http://localhost:51730")
    apply_cors_headers(disallowed, origin="http://evil.example")

    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:51730"
    assert "Access-Control-Allow-Origin" not in disallowed.headers


# 概要・目的: preflight が wildcard origin なしで browser 呼び出しに必要な header を返す。
# テストケース: allowed origin と対象 method/header を指定して preflight response を作る。
# 期待値: HTTP 204、許可 origin、methods、headers が返る。
def test_preflight_response_returns_local_development_cors_headers(settings: Any) -> None:
    settings.HISTORY_API_ALLOWED_ORIGINS = ("http://localhost:51730",)

    response = preflight_response(origin="http://localhost:51730")

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:51730"
    assert response.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert response.headers["Access-Control-Allow-Headers"] == "Content-Type, Authorization"
    assert response.headers["Vary"] == "Origin"

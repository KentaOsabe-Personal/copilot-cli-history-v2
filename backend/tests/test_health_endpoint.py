from django.test import Client
from django.urls import resolve


# 概要・目的: health endpoint が backend の生存確認だけを返す契約を守る。
# テストケース: Django test client で GET /up を要求する。
# 期待値: HTTP 200 と status のみを含む最小 JSON response が返る。
def test_up_endpoint_returns_minimal_success_response() -> None:
    response = Client().get("/up")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# 概要・目的: health response が backend 詳細や履歴情報を漏らさない契約を守る。
# テストケース: GET /up の JSON response keys を確認する。
# 期待値: version、path、history、environment、database 由来の情報を含まない。
def test_up_endpoint_does_not_expose_runtime_or_history_details() -> None:
    response = Client().get("/up")

    assert set(response.json()) == {"status"}
    response_text = response.content.decode().lower()
    for forbidden_fragment in ("version", "path", "history", "environment", "database"):
        assert forbidden_fragment not in response_text


# 概要・目的: root URLconf が /up を foundation の health view に接続する契約を守る。
# テストケース: Django URL resolver で /up を解決する。
# 期待値: /up が health view の up 関数へ解決される。
def test_root_urlconf_resolves_up_to_health_view() -> None:
    match = resolve("/up")

    assert match.func.__module__ == "health.views"
    assert match.func.__name__ == "up"

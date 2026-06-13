from __future__ import annotations

from django.test import Client

from history_api.dependencies import dependency_overrides
from tests.history_api.fakes import CountingRepository, build_history_api_test_repository


def _query(**overrides: str) -> str:
    params = {
        "from": "2026-06-09T00:00:00Z",
        "to": "2026-06-10T00:00:00Z",
    }
    params.update(overrides)
    return "&".join(f"{key}={value}" for key, value in params.items())


# 概要・目的: 一覧 API が有効 range の保存済み summary を frontend 互換 shape で返す。
# テストケース: fake repository を使い、期間指定つきで GET /api/sessions を呼ぶ。
# 期待値: HTTP 200、summary fields、meta.count、partial_results が観測できる。
def test_session_list_api_returns_saved_summaries_with_meta() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(f"/api/sessions?{_query()}")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"count": 2, "partial_results": True}
    assert body["data"][0] == {
        "id": "complete-session",
        "source_format": "current",
        "created_at": "2026-06-09T10:00:00Z",
        "updated_at": "2026-06-09T10:00:00Z",
        "work_context": {
            "cwd": "/workspace",
            "git_root": "/workspace",
            "repository": "repo",
            "branch": "main",
        },
        "selected_model": "gpt-5",
        "source_state": "complete",
        "event_count": 1,
        "message_snapshot_count": 1,
        "conversation_summary": {
            "has_conversation": True,
            "message_count": 1,
            "preview": "complete answer",
            "activity_count": 0,
        },
        "degraded": False,
        "issues": [],
    }
    assert body["data"][1]["degraded"] is True
    assert body["data"][1]["issues"][0]["code"] == "event.partial"


# 概要・目的: 一覧 API の search が保存済み read model の検索 projection に効くことを守る。
# テストケース: complete session にだけ一致する search を指定して GET /api/sessions を呼ぶ。
# 期待値: complete-session だけが返り、partial_results は false になる。
def test_session_list_api_filters_by_search_term() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(f"/api/sessions?{_query(search='complete')}")

    assert response.status_code == 200
    body = response.json()
    assert [session["id"] for session in body["data"]] == ["complete-session"]
    assert body["meta"] == {"count": 1, "partial_results": False}


# 概要・目的: 一致なしの一覧 API が failure ではなく空一覧成功を返す契約を守る。
# テストケース: fake repository に存在しない検索語で GET /api/sessions を呼ぶ。
# 期待値: HTTP 200、data は空配列、meta.count は 0、partial_results は false になる。
def test_session_list_api_returns_empty_success_for_no_matches() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(f"/api/sessions?{_query(search='not-found')}")

    assert response.status_code == 200
    assert response.json() == {
        "data": [],
        "meta": {"count": 0, "partial_results": False},
    }


# 概要・目的: 一覧 API request が保存済み read model の read-only flow に閉じる契約を守る。
# テストケース: call counter 付き fake repository で GET /api/sessions を呼ぶ。
# 期待値: repository の list_sessions だけが呼ばれ、detail / sync / write 系 method は呼ばれない。
def test_session_list_api_uses_read_only_repository_call_pattern() -> None:
    repository = CountingRepository(build_history_api_test_repository())

    with dependency_overrides(repository=repository):
        response = Client().get(f"/api/sessions?{_query()}")

    assert response.status_code == 200
    assert repository.calls == ["list_sessions"]


# 概要・目的: 一覧 API が invalid datetime を既存 error envelope に変換する。
# テストケース: from に日時として解釈できない文字列を指定する。
# 期待値: HTTP 400 と invalid_session_list_query、field/reason/value details が返る。
def test_session_list_api_rejects_invalid_datetime_query() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions?from=not-a-date&to=2026-06-10T00:00:00Z")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_session_list_query",
            "message": "session list query is invalid",
            "details": {
                "field": "from",
                "reason": "invalid_datetime",
                "value": "not-a-date",
            },
        }
    }


# 概要・目的: 一覧 API が無効な期間順序を validation error として返す。
# テストケース: from が to より後になる query で GET /api/sessions を呼ぶ。
# 期待値: HTTP 400 と range field の from_after_to details が返る。
def test_session_list_api_rejects_invalid_range_query() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(
            "/api/sessions?from=2026-06-11T00:00:00Z&to=2026-06-10T00:00:00Z"
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_list_query"
    assert response.json()["error"]["details"] == {
        "field": "range",
        "reason": "from_after_to",
    }


# 概要・目的: 一覧 API が limit の許可範囲外指定を validation error として返す。
# テストケース: limit=0 で GET /api/sessions を呼ぶ。
# 期待値: HTTP 400 と limit field の positive_integer_required details が返る。
def test_session_list_api_rejects_invalid_limit_query() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(f"/api/sessions?{_query(limit='0')}")

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {
        "field": "limit",
        "reason": "positive_integer_required",
        "value": "0",
    }


# 概要・目的: 一覧 API が表示に適さない search 入力を validation error として返す。
# テストケース: 制御文字を含む search で GET /api/sessions を呼ぶ。
# 期待値: HTTP 400 と search field の control_character details が返る。
def test_session_list_api_rejects_invalid_search_query() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get(f"/api/sessions?{_query(search='hello%01')}")

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {
        "field": "search",
        "reason": "control_character",
        "value": "hello\x01",
    }

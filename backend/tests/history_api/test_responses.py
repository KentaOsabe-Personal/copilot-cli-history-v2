import json

from django.http import JsonResponse

from history_api.query_validation import QueryValidationError
from history_api.responses import error_response, repository_error_response, success_response
from history_read_model.repository import RepositoryError


def _json_body(response: JsonResponse) -> object:
    return json.loads(response.content)


# 概要・目的: 成功 response が JsonResponse として既存 envelope に包まれる契約を守る。
# テストケース: data と meta を指定して success response を生成する。
# 期待値: HTTP 200 と data/meta の JSON body が返る。
def test_success_response_wraps_data_and_meta() -> None:
    response = success_response([{"id": "complete-session"}], meta={"count": 1})

    assert isinstance(response, JsonResponse)
    assert response.status_code == 200
    assert _json_body(response) == {"data": [{"id": "complete-session"}], "meta": {"count": 1}}


# 概要・目的: validation error が frontend 互換 error envelope に変換される契約を守る。
# テストケース: invalid_session_list_query 用の QueryValidationError を response 化する。
# 期待値: HTTP 400 と error.code/message/details を持つ body が返る。
def test_validation_error_response_uses_invalid_session_list_query_envelope() -> None:
    response = error_response(
        "invalid_session_list_query",
        "session list query is invalid",
        status=400,
        details=QueryValidationError(field="from", reason="invalid_datetime", value="bad"),
    )

    assert response.status_code == 400
    assert _json_body(response) == {
        "error": {
            "code": "invalid_session_list_query",
            "message": "session list query is invalid",
            "details": {"field": "from", "reason": "invalid_datetime", "value": "bad"},
        }
    }


# 概要・目的: repository failure が frontend で service failure と識別できる envelope になる。
# テストケース: credentials_error と query_failed を repository error response に変換する。
# 期待値: credentials_error は 503、query_failed は 500 の history_api_failed として返る。
def test_repository_error_response_maps_status_by_error_kind() -> None:
    credentials_response = repository_error_response(
        RepositoryError(kind="credentials_error", message="missing credentials")
    )
    query_response = repository_error_response(
        RepositoryError(kind="query_failed", message="query failed", details={"job": "abc"})
    )

    assert credentials_response.status_code == 503
    credentials_body = _json_body(credentials_response)
    query_body = _json_body(query_response)
    assert isinstance(credentials_body, dict)
    assert isinstance(query_body, dict)
    assert credentials_body["error"]["code"] == "history_api_failed"
    assert credentials_body["error"]["details"] == {"kind": "credentials_error"}
    assert query_response.status_code == 500
    assert query_body["error"]["details"] == {"kind": "query_failed", "job": "abc"}

from __future__ import annotations

from django.test import Client

from history_api.dependencies import dependency_overrides
from history_read_model.fake_repository import FakeBigQueryReadModelRepository
from history_read_model.repository import (
    RepositoryError,
    RepositoryExecutionOptions,
    SessionDetailResult,
)
from tests.history_api.fakes import build_history_api_test_repository


class FailingDetailRepository(FakeBigQueryReadModelRepository):
    def get_session_detail(
        self,
        session_id: str,
        options: RepositoryExecutionOptions | None = None,
    ) -> SessionDetailResult:
        _ = session_id, options
        return SessionDetailResult.failure(
            RepositoryError(kind="query_failed", message="fake detail lookup failed")
        )


# 概要・目的: 詳細 API が default では保存済み raw payload を抑制する契約を守る。
# テストケース: include_raw なしで complete session の詳細 endpoint を呼ぶ。
# 期待値: raw_included false、raw_payload null、conversation/activity/timeline shape が返る。
def test_session_detail_api_suppresses_raw_payload_by_default() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions/complete-session")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["raw_included"] is False
    assert data["message_snapshots"][0]["raw_payload"] is None
    assert data["conversation"] == {
        "entries": [],
        "message_count": 0,
        "empty_reason": None,
        "summary": {
            "has_conversation": True,
            "message_count": 1,
            "preview": "complete answer",
            "activity_count": 0,
        },
    }
    assert data["activity"] == {"entries": []}
    assert data["timeline"] == []
    assert data["degraded"] is False
    assert data["issues"] == []


# 概要・目的: 詳細 API が include_raw=true の opt-in で保存済み raw payload を返す。
# テストケース: complete session の default response と raw response を続けて取得する。
# 期待値: raw inclusion だけが切り替わり、raw 以外の detail contract は同一である。
def test_session_detail_api_returns_raw_payload_only_when_opted_in() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        default_response = Client().get("/api/sessions/complete-session")
        raw_response = Client().get("/api/sessions/complete-session?include_raw=true")

    default_data = default_response.json()["data"]
    raw_data = raw_response.json()["data"]
    assert raw_response.status_code == 200
    assert default_data["raw_included"] is False
    assert raw_data["raw_included"] is True
    assert default_data["message_snapshots"][0]["raw_payload"] is None
    assert raw_data["message_snapshots"][0]["raw_payload"] == {
        "type": "assistant.message",
        "content": "complete answer",
    }
    comparable_default = dict(default_data)
    comparable_raw = dict(raw_data)
    comparable_default["raw_included"] = True
    comparable_default["message_snapshots"][0]["raw_payload"] = comparable_raw[
        "message_snapshots"
    ][0]["raw_payload"]
    assert comparable_default == comparable_raw


# 概要・目的: 詳細 API が degraded detail の issue/degraded shape を保持する契約を守る。
# テストケース: degraded session の詳細 endpoint を呼ぶ。
# 期待値: HTTP 200、degraded true、conversation empty_reason と issues が観測できる。
def test_session_detail_api_returns_degraded_detail_shape() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions/degraded-session")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["degraded"] is True
    assert data["conversation"]["empty_reason"] == "no_conversation_messages"
    assert data["activity"] == {"entries": []}
    assert data["timeline"] == []
    assert data["issues"] == []


# 概要・目的: 詳細 API が missing session を repository failure と混同しない契約を守る。
# テストケース: fake repository にない session ID で詳細 endpoint を呼ぶ。
# 期待値: HTTP 404 と session_not_found error envelope が返る。
def test_session_detail_api_returns_not_found_error() -> None:
    with dependency_overrides(repository=build_history_api_test_repository()):
        response = Client().get("/api/sessions/missing-session")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "session_not_found",
            "message": "Session was not found.",
            "details": {"session_id": "missing-session"},
        }
    }


# 概要・目的: 詳細 API が repository failure を service failure envelope に変換する。
# テストケース: detail lookup が query_failed を返す repository で詳細 endpoint を呼ぶ。
# 期待値: HTTP 500 と history_api_failed、repository kind details が返る。
def test_session_detail_api_returns_repository_failure_error() -> None:
    with dependency_overrides(repository=FailingDetailRepository()):
        response = Client().get("/api/sessions/complete-session")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "history_api_failed",
            "message": "History API request failed.",
            "details": {"kind": "query_failed"},
        }
    }

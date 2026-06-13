from __future__ import annotations

from datetime import UTC, datetime

from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria
from tests.history_api.fakes import build_history_api_test_repository


# 概要・目的: API request tests が一覧、degraded、詳細、raw 詳細を表せる fake data を共有する。
# テストケース: history API 用 fake repository builder から session list と detail を取得する。
# 期待値: summary は通常/degraded の代表値を持ち、detail は raw opt-in 可能な payload を持つ。
def test_build_history_api_test_repository_provides_representative_session_data() -> None:
    repository = build_history_api_test_repository()

    list_result = repository.list_sessions(
        SessionListCriteria(
            from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
            to_datetime=datetime(2026, 6, 30, tzinfo=UTC),
        ),
        RepositoryExecutionOptions(),
    )
    detail_result = repository.get_session_detail("complete-session", RepositoryExecutionOptions())

    assert list_result.ok is True
    assert len(list_result.summary_payloads) == 2
    assert list_result.summary_payloads[0]["id"] == "complete-session"
    assert list_result.summary_payloads[1]["degraded"] is True
    assert detail_result.ok is True
    assert detail_result.detail_payload is not None
    assert detail_result.detail_payload["raw_included"] is True
    assert detail_result.detail_payload["message_snapshots"] == [
        {
            "role": "assistant",
            "content": "complete answer",
            "raw_payload": {"type": "assistant.message", "content": "complete answer"},
        }
    ]


# 概要・目的: API request tests が sync success / conflict / failure の fake 状態を
# 作れることを守る。
# テストケース: running sync を含む fake repository と save failure repository を
# builder から取得する。
# 期待値: running lookup は開始済み ID を返し、save failure mode は repository error を返す。
def test_build_history_api_test_repository_provides_sync_states() -> None:
    running_repository = build_history_api_test_repository(sync_state="running")
    failing_repository = build_history_api_test_repository(sync_state="save_failure")

    running = running_repository.find_running_sync_run(RepositoryExecutionOptions())
    failed = failing_repository.save_sessions((), RepositoryExecutionOptions())

    assert running.ok is True
    assert running.found is True
    assert running.sync_run_id == "sync-running"
    assert running.started_at is not None
    assert failed.ok is False
    assert failed.error is not None
    assert failed.error.kind == "query_failed"

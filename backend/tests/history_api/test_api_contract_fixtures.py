from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Literal
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import Client

from copilot_history.types import ReadFailureResult
from history_api.dependencies import dependency_overrides
from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
)
from history_read_model.repository import (
    RepositoryError,
    RepositoryExecutionOptions,
    SyncWriteResult,
)
from tests.copilot_history.api_contract_fixtures import (
    ApiContractFixtureRepository,
    assert_fixture_body_matches,
)
from tests.history_api.fakes import (
    FakeSyncReader,
    degraded_issue,
    normalized_session,
    sync_reader_success,
)

JsonObject = dict[str, object]
SyncScenarioKind = Literal["success", "degraded", "conflict", "root_failure", "save_failure"]

FIXTURES = ApiContractFixtureRepository.default()


class ContractSaveFailureRepository(FakeBigQueryReadModelRepository):
    def save_sessions(
        self,
        rows: Sequence[object],
        options: RepositoryExecutionOptions | None = None,
    ) -> SyncWriteResult:
        _ = rows, options
        return SyncWriteResult.failure(
            RepositoryError(
                kind="query_failed",
                message="record invalid",
                details={"failure_class": "ActiveRecord::RecordInvalid"},
            )
        )


def _scenario_request(scenario_id: str) -> JsonObject:
    return FIXTURES.request(scenario_id)


def _expected_body(scenario_id: str) -> JsonObject:
    return FIXTURES.expected_body(scenario_id)


def _expected_status(scenario_id: str) -> int:
    status = FIXTURES.expected_response(scenario_id)["status"]
    if not isinstance(status, int):
        raise AssertionError(f"fixture response status must be an int: {scenario_id}")
    return status


def _client_response(scenario_id: str) -> tuple[int, JsonObject]:
    request = _scenario_request(scenario_id)
    method = str(request["method"])
    path = str(request["path"])
    query = request.get("query")
    if isinstance(query, Mapping) and query:
        path = f"{path}?{urlencode(query)}"

    client = Client()
    if method == "GET":
        response = client.get(path)
    elif method == "POST":
        response = client.post(path)
    else:
        raise AssertionError(f"unsupported fixture method: {method}")
    return response.status_code, response.json()


def _assert_contract_response(scenario_id: str) -> None:
    status, body = _client_response(scenario_id)
    expected_status = _expected_status(scenario_id)
    assert status == expected_status, (
        f"API contract fixture status mismatch for {scenario_id}: "
        f"expected {expected_status}; actual {status}"
    )
    assert_fixture_body_matches(FIXTURES, scenario_id, body)


@contextmanager
def _contract_repository_for(scenario_id: str) -> Iterator[None]:
    repository = FakeBigQueryReadModelRepository()
    if scenario_id == "sessions.index.list_success":
        for payload in _object_list(_expected_body(scenario_id)["data"]):
            repository.save_session(_session_row_from_summary(payload))
    elif scenario_id == "sessions.index.list_degraded":
        for payload in _object_list(_expected_body(scenario_id)["data"]):
            repository.save_session(_session_row_from_summary(payload))
    elif scenario_id.startswith("sessions.show.") and scenario_id != "sessions.show.not_found":
        repository.save_session(_session_row_from_detail(_expected_body(scenario_id)["data"]))
    with dependency_overrides(repository=repository):
        yield


@contextmanager
def _contract_sync_for(kind: SyncScenarioKind) -> Iterator[None]:
    repository: FakeBigQueryReadModelRepository
    reader: object
    sync_run_id: str
    clock_values: tuple[datetime, ...]

    if kind == "success":
        repository = FakeBigQueryReadModelRepository()
        reader = FakeSyncReader(
            sync_reader_success(
                normalized_session("current-schema-mixed"),
                normalized_session("legacy-schema-mixed", source_state="complete"),
            )
        )
        sync_run_id = "101"
        clock_values = (_dt("2026-04-30T08:55:00Z"), _dt("2026-04-30T08:55:01Z"))
    elif kind == "degraded":
        repository = FakeBigQueryReadModelRepository()
        reader = FakeSyncReader(
            sync_reader_success(
                normalized_session("current-schema-mixed"),
                normalized_session(
                    "current-schema-degraded",
                    source_state="degraded",
                    issues=(degraded_issue(),),
                ),
            )
        )
        sync_run_id = "102"
        clock_values = (_dt("2026-04-30T08:56:00Z"), _dt("2026-04-30T08:56:02Z"))
    elif kind == "conflict":
        repository = FakeBigQueryReadModelRepository()
        repository.save_sync_run(_running_sync_run_row())
        reader = FakeSyncReader(sync_reader_success())
        sync_run_id = "999"
        clock_values = (_dt("2026-04-30T08:59:00Z"),)
    elif kind == "root_failure":
        repository = FakeBigQueryReadModelRepository()
        reader = FakeSyncReader(
            ReadFailureResult(
                code="root_missing",
                message="history root does not exist",
                root_path="/tmp/copilot-missing-home/.copilot",
            )
        )
        sync_run_id = "103"
        clock_values = (_dt("2026-04-30T08:57:00Z"), _dt("2026-04-30T08:57:01Z"))
    else:
        repository = ContractSaveFailureRepository()
        reader = FakeSyncReader(sync_reader_success())
        sync_run_id = "104"
        clock_values = (_dt("2026-04-30T08:58:00Z"), _dt("2026-04-30T08:58:01Z"))

    clock = _sequence_clock(clock_values)
    with (
        dependency_overrides(repository=repository, reader=reader, clock=clock),
        patch(
            "history_api.services.HistoryApiService._default_sync_run_id",
            return_value=sync_run_id,
        ),
    ):
        yield


def _sequence_clock(values: tuple[datetime, ...]) -> Callable[[], datetime]:
    iterator = iter(values)
    last = values[-1]

    def clock() -> datetime:
        nonlocal last
        try:
            last = next(iterator)
        except StopIteration:
            return last
        return last

    return clock


def _session_row_from_summary(value: object) -> CopilotSessionRow:
    if not isinstance(value, dict):
        raise AssertionError("summary fixture payload must be an object")
    session_id = str(value["id"])
    created_at = _dt(str(value["created_at"]))
    updated_at = _dt(str(value["updated_at"]))
    work_context = _mapping(value.get("work_context"))
    conversation_summary = _mapping(value.get("conversation_summary"))
    issues = value.get("issues")
    return CopilotSessionRow(
        session_id=session_id,
        source_format=str(value["source_format"]),
        source_state=str(value["source_state"]),
        created_at_source=created_at,
        updated_at_source=updated_at,
        source_partition_date=created_at.date(),
        cwd=_optional_str(work_context.get("cwd")),
        git_root=_optional_str(work_context.get("git_root")),
        repository=_optional_str(work_context.get("repository")),
        branch=_optional_str(work_context.get("branch")),
        selected_model=_optional_str(value.get("selected_model")),
        event_count=_int(value["event_count"]),
        message_snapshot_count=_int(value["message_snapshot_count"]),
        issue_count=len(issues) if isinstance(issues, list) else 0,
        message_count=_int(conversation_summary.get("message_count", 0)),
        activity_count=_int(conversation_summary.get("activity_count", 0)),
        degraded=value.get("degraded") is True,
        conversation_preview=_optional_str(conversation_summary.get("preview")),
        source_paths={"fixture": f"/tmp/{session_id}.json"},
        source_fingerprint={"fixture": session_id},
        summary_payload=value,
        detail_payload={"id": session_id, "raw_included": True},
        search_text=str(conversation_summary.get("preview") or ""),
        search_text_version=2,
        indexed_at=updated_at,
    )


def _session_row_from_detail(value: object) -> CopilotSessionRow:
    if not isinstance(value, dict):
        raise AssertionError("detail fixture payload must be an object")
    summary = _summary_from_detail(value)
    row = _session_row_from_summary(summary)
    return CopilotSessionRow(
        **{
            **row.__dict__,
            "detail_payload": value,
        }
    )


def _summary_from_detail(value: Mapping[str, object]) -> JsonObject:
    conversation = _mapping(value.get("conversation"))
    summary = _mapping(conversation.get("summary"))
    return {
        "id": value["id"],
        "source_format": value.get("source_format", "current"),
        "created_at": value.get("created_at", "2026-04-28T04:00:01Z"),
        "updated_at": value.get("updated_at", "2026-04-28T04:00:02Z"),
        "work_context": value.get(
            "work_context",
            {"cwd": None, "git_root": None, "repository": None, "branch": None},
        ),
        "selected_model": value.get("selected_model"),
        "source_state": value.get("source_state", "complete"),
        "event_count": (
            len(_object_list(value.get("timeline", [])))
            if isinstance(value.get("timeline"), list)
            else 0
        ),
        "message_snapshot_count": (
            len(_object_list(value.get("message_snapshots", [])))
            if isinstance(value.get("message_snapshots"), list)
            else 0
        ),
        "conversation_summary": {
            "has_conversation": summary.get("has_conversation", True),
            "message_count": summary.get("message_count", 0),
            "preview": summary.get("preview"),
            "activity_count": summary.get("activity_count", 0),
        },
        "degraded": value.get("degraded", False),
        "issues": value.get("issues", []),
    }


def _running_sync_run_row() -> HistorySyncRunRow:
    started_at = _dt("2026-04-30T08:55:00Z")
    return HistorySyncRunRow(
        sync_run_id="100",
        status="running",
        started_at=started_at,
        finished_at=None,
        started_partition_date=date(2026, 4, 30),
        processed_count=0,
        inserted_count=0,
        updated_count=0,
        saved_count=0,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key="history-sync",
        indexed_at=started_at,
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _object_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("fixture value must be a list")
    return value


def _int(value: object) -> int:
    if not isinstance(value, int):
        raise AssertionError("fixture value must be an int")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


# 概要・目的: Contract fixture の一覧系 scenario と Django response の互換性を守る。
# テストケース: list、empty、search empty、degraded の fixture request を API に送る。
# 期待値: HTTP status と body が fixture の expected response と一致する。
def test_contract_fixture_session_list_scenarios_match_django_response() -> None:
    for scenario_id in (
        "sessions.index.list_success",
        "sessions.index.list_empty",
        "sessions.index.list_search_empty",
        "sessions.index.list_degraded",
    ):
        with _contract_repository_for(scenario_id):
            _assert_contract_response(scenario_id)


# 概要・目的: Contract fixture の詳細系 scenario と Django response の互換性を守る。
# テストケース: detail、raw detail、not found の fixture request を API に送る。
# 期待値: HTTP status と body が fixture の expected response と一致する。
def test_contract_fixture_session_detail_scenarios_match_django_response() -> None:
    for scenario_id in (
        "sessions.show.detail_success",
        "sessions.show.detail_with_raw",
        "sessions.show.not_found",
    ):
        with _contract_repository_for(scenario_id):
            _assert_contract_response(scenario_id)


# 概要・目的: Contract fixture の validation error と Django response の互換性を守る。
# テストケース: invalid datetime/range/limit/search の fixture request を API に送る。
# 期待値: HTTP 400 と error body が fixture の expected response と一致する。
def test_contract_fixture_validation_scenarios_match_django_response() -> None:
    for scenario_id in (
        "sessions.index.invalid_date_range",
        "sessions.index.invalid_datetime",
        "sessions.index.invalid_limit",
        "sessions.index.invalid_search_control_character",
        "sessions.index.overlong_search",
    ):
        with _contract_repository_for(scenario_id):
            _assert_contract_response(scenario_id)


# 概要・目的: Contract fixture の同期系 scenario と Django response の互換性を守る。
# テストケース: success、completed_with_issues、conflict、root failure、save failure を送る。
# 期待値: HTTP status と body が fixture の expected response と一致する。
def test_contract_fixture_history_sync_scenarios_match_django_response() -> None:
    scenarios: tuple[tuple[str, SyncScenarioKind], ...] = (
        ("history_sync.success", "success"),
        ("history_sync.completed_with_issues", "degraded"),
        ("history_sync.conflict", "conflict"),
        ("history_sync.root_failure", "root_failure"),
        ("history_sync.persistence_failure", "save_failure"),
    )
    for scenario_id, kind in scenarios:
        with _contract_sync_for(kind):
            _assert_contract_response(scenario_id)


# 概要・目的: Contract fixture body mismatch の診断が scenario と差分 path を示す契約を守る。
# テストケース: 意図的に meta.count を壊した body を fixture 比較 helper に渡す。
# 期待値: AssertionError に scenario ID と JSON path が含まれる。
def test_contract_fixture_body_mismatch_reports_scenario_and_field_path() -> None:
    broken_body = dict(_expected_body("sessions.index.list_empty"))
    broken_body["meta"] = {"count": 99, "partial_results": False}

    try:
        assert_fixture_body_matches(FIXTURES, "sessions.index.list_empty", broken_body)
    except AssertionError as error:
        message = str(error)
    else:
        raise AssertionError("fixture comparison should fail")

    assert "sessions.index.list_empty" in message
    assert "$.meta.count" in message

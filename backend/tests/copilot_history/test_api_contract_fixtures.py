import json
from pathlib import Path

import pytest

from tests.copilot_history.api_contract_fixtures import (
    ApiContractFixtureRepository,
    assert_fixture_body_matches,
)


# 概要・目的: api-contract-fixtures の manifest と response body を
# scenario id から取得できる契約を守る。
# テストケース: sessions.index.list_success の scenario metadata と expected body を読む。
# 期待値: manifest の status と response body が fixture JSON の内容と一致する。
def test_contract_fixture_repository_loads_response_body_by_scenario_id() -> None:
    repository = ApiContractFixtureRepository.default()
    scenario = repository.scenario("sessions.index.list_success")
    body = repository.expected_body("sessions.index.list_success")

    assert scenario.id == "sessions.index.list_success"
    assert scenario.response_path.as_posix() == "sessions/index/list_success.response.json"
    assert scenario.status == 200
    assert body["meta"] == {"count": 2, "partial_results": False}
    data = body["data"]
    assert isinstance(data, list)
    first_summary = data[0]
    assert isinstance(first_summary, dict)
    assert first_summary["id"] == "current-schema-mixed"


# 概要・目的: fixture repository が代表 scenario の一覧を manifest 順で返す契約を守る。
# テストケース: success payload_kind の scenario id を抽出する。
# 期待値: list、detail、history sync の代表 success scenario を manifest 順で取得できる。
def test_contract_fixture_repository_filters_scenarios_in_manifest_order() -> None:
    repository = ApiContractFixtureRepository.default()

    success_ids = [scenario.id for scenario in repository.scenarios(payload_kind="success")]

    assert success_ids[:3] == [
        "sessions.index.list_success",
        "sessions.index.list_empty",
        "sessions.index.list_search_empty",
    ]
    assert "sessions.show.detail_with_raw" in success_ids
    assert "history_sync.success" in success_ids


# 概要・目的: fixture deep equality の失敗時に scenario id と field path を表示する契約を守る。
# テストケース: list_success の generated body だけ meta.count を意図的に変更して比較する。
# 期待値: AssertionError に scenario id と最初に差分が出た $.meta.count が含まれる。
def test_assert_fixture_body_matches_reports_scenario_id_and_first_diff_path() -> None:
    repository = ApiContractFixtureRepository.default()
    generated_body = dict(repository.expected_body("sessions.index.list_success"))
    generated_body["meta"] = {"count": 999, "partial_results": False}

    with pytest.raises(AssertionError) as error:
        assert_fixture_body_matches(
            repository,
            "sessions.index.list_success",
            generated_body,
        )

    message = str(error.value)
    assert "sessions.index.list_success" in message
    assert "$.meta.count" in message
    assert "expected 2" in message
    assert "actual 999" in message


# 概要・目的: fixture deep equality helper が nested list / object の
# 最初の差分 path を安定して返す契約を守る。
# テストケース: detail fixture の timeline 先頭 event kind を意図的に変更して比較する。
# 期待値: AssertionError に $.data.timeline[0].kind が含まれる。
def test_assert_fixture_body_matches_reports_nested_list_diff_path() -> None:
    repository = ApiContractFixtureRepository.default()
    generated_body = json.loads(
        json.dumps(repository.expected_body("sessions.show.detail_success"))
    )
    generated_body["data"]["timeline"][0]["kind"] = "unknown"

    with pytest.raises(AssertionError) as error:
        assert_fixture_body_matches(
            repository,
            "sessions.show.detail_success",
            generated_body,
        )

    assert "$.data.timeline[0].kind" in str(error.value)


# 概要・目的: fixture root が見つからない場合に誤った fixture 比較を進めない契約を守る。
# テストケース: 存在しない root path を明示して repository を生成する。
# 期待値: manifest 読込前に FileNotFoundError で失敗する。
def test_contract_fixture_repository_rejects_missing_fixture_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-fixtures"

    with pytest.raises(FileNotFoundError, match="api-contract-fixtures"):
        ApiContractFixtureRepository(missing_root)

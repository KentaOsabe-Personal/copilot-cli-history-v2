from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

type JsonObject = dict[str, object]
type JsonValue = object


@dataclass(frozen=True)
class ApiContractScenario:
    id: str
    method: str
    endpoint: str
    status: int
    payload_kind: str
    request_path: Path
    response_path: Path
    requirements: tuple[str, ...]
    frontend_types: tuple[str, ...]


@dataclass(frozen=True)
class FirstDiff:
    path: str
    expected: JsonValue
    actual: JsonValue


class ApiContractFixtureRepository:
    def __init__(self, fixture_root: Path) -> None:
        self._fixture_root = fixture_root
        self._manifest_path = fixture_root / "manifest.json"
        if not self._manifest_path.exists():
            msg = f"api-contract-fixtures manifest not found: {self._manifest_path}"
            raise FileNotFoundError(msg)
        manifest = self._read_json(self._manifest_path)
        if not isinstance(manifest, dict):
            msg = f"api-contract-fixtures manifest must be a JSON object: {self._manifest_path}"
            raise TypeError(msg)
        self._manifest = manifest
        self._scenarios = tuple(
            self._scenario_from(raw_scenario)
            for raw_scenario in self._manifest_mapping_sequence("scenarios")
        )
        self._scenarios_by_id = {scenario.id: scenario for scenario in self._scenarios}

    @classmethod
    def default(cls) -> ApiContractFixtureRepository:
        return cls(_default_fixture_root())

    def scenarios(self, *, payload_kind: str | None = None) -> tuple[ApiContractScenario, ...]:
        if payload_kind is None:
            return self._scenarios
        return tuple(
            scenario for scenario in self._scenarios if scenario.payload_kind == payload_kind
        )

    def scenario(self, scenario_id: str) -> ApiContractScenario:
        try:
            return self._scenarios_by_id[scenario_id]
        except KeyError as error:
            msg = f"unknown api contract fixture scenario: {scenario_id}"
            raise KeyError(msg) from error

    def expected_response(self, scenario_id: str) -> JsonObject:
        scenario = self.scenario(scenario_id)
        response = self._read_fixture_json(scenario.response_path)
        if not isinstance(response, dict):
            msg = f"response fixture must be a JSON object: {scenario.response_path}"
            raise TypeError(msg)
        return response

    def request(self, scenario_id: str) -> JsonObject:
        scenario = self.scenario(scenario_id)
        request = self._read_fixture_json(scenario.request_path)
        if not isinstance(request, dict):
            msg = f"request fixture must be a JSON object: {scenario.request_path}"
            raise TypeError(msg)
        return request

    def expected_body(self, scenario_id: str) -> JsonObject:
        response = self.expected_response(scenario_id)
        body = response.get("body")
        if not isinstance(body, dict):
            msg = f"response body must be a JSON object: {scenario_id}"
            raise TypeError(msg)
        return body

    def _manifest_mapping_sequence(self, key: str) -> Iterator[Mapping[str, object]]:
        value = self._manifest.get(key)
        if not isinstance(value, list):
            msg = f"manifest {key} must be a list"
            raise TypeError(msg)
        for item in value:
            if not isinstance(item, dict):
                msg = f"manifest {key} entries must be objects"
                raise TypeError(msg)
            yield item

    def _scenario_from(self, raw_scenario: Mapping[str, object]) -> ApiContractScenario:
        return ApiContractScenario(
            id=_required_str(raw_scenario, "id"),
            method=_required_str(raw_scenario, "method"),
            endpoint=_required_str(raw_scenario, "endpoint"),
            status=_required_int(raw_scenario, "status"),
            payload_kind=_required_str(raw_scenario, "payload_kind"),
            request_path=Path(_required_str(raw_scenario, "request")),
            response_path=Path(_required_str(raw_scenario, "response")),
            requirements=_required_str_tuple(raw_scenario, "requirements"),
            frontend_types=_required_str_tuple(raw_scenario, "frontend_types"),
        )

    def _read_fixture_json(self, relative_path: Path) -> JsonValue:
        return self._read_json(self._fixture_root / relative_path)

    def _read_json(self, path: Path) -> JsonValue:
        with path.open(encoding="utf-8") as file:
            return json.load(file)


def assert_fixture_body_matches(
    repository: ApiContractFixtureRepository,
    scenario_id: str,
    generated_body: JsonObject,
) -> None:
    expected_body = repository.expected_body(scenario_id)
    diff = first_json_diff(expected_body, generated_body)
    if diff is None:
        return
    expected = _format_json_value(diff.expected)
    actual = _format_json_value(diff.actual)
    msg = (
        f"API contract fixture mismatch for {scenario_id} at {diff.path}: "
        f"expected {expected}; actual {actual}"
    )
    raise AssertionError(msg)


def first_json_diff(expected: JsonValue, actual: JsonValue, path: str = "$") -> FirstDiff | None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        return _first_mapping_diff(expected, actual, path)
    if isinstance(expected, list) and isinstance(actual, list):
        return _first_sequence_diff(expected, actual, path)
    if expected != actual:
        return FirstDiff(path=path, expected=expected, actual=actual)
    return None


def _first_mapping_diff(
    expected: Mapping[str, object], actual: Mapping[str, object], path: str
) -> FirstDiff | None:
    for key in expected:
        child_path = f"{path}.{key}"
        if key not in actual:
            return FirstDiff(path=child_path, expected=expected[key], actual="<missing>")
        diff = first_json_diff(expected[key], actual[key], child_path)
        if diff is not None:
            return diff
    for key in actual:
        if key not in expected:
            return FirstDiff(path=f"{path}.{key}", expected="<missing>", actual=actual[key])
    return None


def _first_sequence_diff(
    expected: Sequence[object], actual: Sequence[object], path: str
) -> FirstDiff | None:
    for index, expected_item in enumerate(expected):
        child_path = f"{path}[{index}]"
        if index >= len(actual):
            return FirstDiff(path=child_path, expected=expected_item, actual="<missing>")
        diff = first_json_diff(expected_item, actual[index], child_path)
        if diff is not None:
            return diff
    if len(actual) > len(expected):
        return FirstDiff(
            path=f"{path}[{len(expected)}]", expected="<missing>", actual=actual[len(expected)]
        )
    return None


def _default_fixture_root() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    repo_root = backend_root.parent
    candidates = (
        repo_root / ".kiro" / "specs" / "api-contract-fixtures" / "fixtures",
        Path("/workspace/.kiro/specs/api-contract-fixtures/fixtures"),
    )
    for candidate in candidates:
        if (candidate / "manifest.json").exists():
            return candidate
    msg = "api-contract-fixtures manifest not found in known fixture roots"
    raise FileNotFoundError(msg)


def _required_str(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str):
        msg = f"{key} must be a string"
        raise TypeError(msg)
    return value


def _required_int(values: Mapping[str, object], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int):
        msg = f"{key} must be an integer"
        raise TypeError(msg)
    return value


def _required_str_tuple(values: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"{key} must be a list of strings"
        raise TypeError(msg)
    return tuple(value)


def _format_json_value(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

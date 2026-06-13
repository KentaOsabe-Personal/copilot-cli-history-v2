from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import pytest
from django.conf import settings

from history_read_model.bigquery_settings import read_bigquery_integration_enabled
from history_read_model.fake_repository import FakeBigQueryReadModelRepository


class _ReaderDouble:
    def read(self) -> NoReturn:
        raise AssertionError("reader double should not be executed in dependency tests")


# 概要・目的: Django settings が History API の runtime 設定を credentials なしで公開する。
# テストケース: settings import 後に installed app、repository backend、allowed origins を読む。
# 期待値: history_api が有効で、fake backend、local frontend origin、integration opt-in が読める。
def test_history_api_settings_are_available_without_bigquery_client() -> None:
    assert "history_api" in settings.INSTALLED_APPS
    assert settings.HISTORY_API_REPOSITORY_BACKEND == "fake"
    assert settings.HISTORY_API_ALLOWED_ORIGINS == (
        "http://localhost:51730",
        "http://127.0.0.1:51730",
    )
    assert settings.HISTORY_API_BIGQUERY_INTEGRATION_ENABLED is read_bigquery_integration_enabled()


# 概要・目的: API tests が実 BigQuery 接続なしで dependency を fake に差し替えられることを守る。
# テストケース: dependency override context 内で repository、reader、clock を設定して取得する。
# 期待値: override 中だけ同じ object が返り、終了後は override が残らず default reader に戻る。
def test_history_api_dependency_override_is_scoped() -> None:
    from history_api.dependencies import (
        dependency_overrides,
        get_clock,
        get_reader,
        get_repository,
    )

    repository = FakeBigQueryReadModelRepository()
    reader = _ReaderDouble()
    fixed_now = datetime(2026, 6, 9, 10, tzinfo=UTC)

    with dependency_overrides(
        repository=repository,
        reader=reader,
        clock=lambda: fixed_now,
    ):
        assert get_repository() is repository
        assert get_reader() is reader
        assert get_clock()() == fixed_now

    assert get_repository() is not repository
    assert get_reader() is not reader
    assert get_reader().__class__.__name__ == "SessionCatalogReader"


# 概要・目的: BigQuery repository は明示 backend 選択時だけ遅延生成される契約を守る。
# テストケース: settings override で BigQuery backend を指定し、settings loader と
# client factory を stub する。
# 期待値: get_repository 呼び出し時に初めて BigQuery repository が生成される。
def test_history_api_bigquery_repository_is_created_lazily(settings: Any) -> None:
    from history_api import dependencies
    from history_read_model.bigquery_settings import BigQueryReadModelSettings

    calls: list[str] = []

    def load_settings(*, require_credentials: bool) -> BigQueryReadModelSettings:
        calls.append(f"settings:{require_credentials}")
        return BigQueryReadModelSettings(
            project_id="local-project",
            dataset_id="history",
            location="US",
            table_prefix="dev_",
            credentials_path=None,
        )

    def client_factory(project_id: str) -> object:
        calls.append(f"client:{project_id}")
        return object()

    settings.HISTORY_API_REPOSITORY_BACKEND = "bigquery"

    with dependencies.dependency_overrides(
        bigquery_settings_loader=load_settings,
        bigquery_client_factory=client_factory,
    ):
        assert calls == []
        repository = dependencies.get_repository()

    assert repository.__class__.__name__ == "BigQuerySessionReadModelRepository"
    assert calls == ["settings:True", "client:local-project"]


# 概要・目的: BigQuery backend 選択時も実接続 precondition 不足を client 生成前に識別する。
# テストケース: opt-in 相当の backend 設定で必須 env と credentials を未設定にする。
# 期待値: BigQuerySettingsError が発生し、BigQuery client factory は呼ばれない。
def test_history_api_bigquery_entrypoint_reports_missing_preconditions_before_client(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from history_api import dependencies
    from history_read_model.bigquery_settings import BigQuerySettingsError, load_bigquery_settings

    for key in (
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET_ID",
        "BIGQUERY_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    settings.HISTORY_API_REPOSITORY_BACKEND = "bigquery"
    client_calls: list[str] = []

    def client_factory(project_id: str) -> object:
        client_calls.append(project_id)
        return object()

    with (
        dependencies.dependency_overrides(
            bigquery_settings_loader=load_bigquery_settings,
            bigquery_client_factory=client_factory,
        ),
        pytest.raises(BigQuerySettingsError) as exc_info,
    ):
        dependencies.get_repository()

    assert "BIGQUERY_PROJECT_ID" in exc_info.value.missing_settings
    assert "BIGQUERY_DATASET_ID" in exc_info.value.missing_settings
    assert client_calls == []


# 概要・目的: credentials がない通常環境でも fake repository による API 検証入口が継続する。
# テストケース: BigQuery 関連 env を未設定にし、default backend の repository を取得する。
# 期待値: 実 BigQuery client を要求せず FakeBigQueryReadModelRepository が返る。
def test_history_api_default_fake_entrypoint_continues_without_bigquery_credentials(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from history_api import dependencies

    for key in (
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET_ID",
        "BIGQUERY_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)
    settings.HISTORY_API_REPOSITORY_BACKEND = "fake"

    with dependencies.dependency_overrides():
        repository = dependencies.get_repository()

    assert isinstance(repository, FakeBigQueryReadModelRepository)

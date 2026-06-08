import importlib
import tomllib
from pathlib import Path

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.urls import Resolver404, resolve


# 概要・目的: Django project の settings が外部サービスなしで読み込める契約を守る。
# テストケース: settings module を import し、最小 database と URLconf を確認する。
# 期待値: sqlite default DB と backend_config.urls が設定され、
# BigQuery/MySQL/raw files を要求しない。
def test_settings_import_uses_minimal_sqlite_configuration() -> None:
    settings = importlib.import_module("backend_config.settings")

    assert settings.ROOT_URLCONF == "backend_config.urls"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert "bigquery" not in repr(settings.DATABASES).lower()
    assert "mysql" not in repr(settings.DATABASES).lower()
    assert "COPILOT_HOME" not in vars(settings)


# 概要・目的: BigQuery read model app が Django の app registry で discover される契約を守る。
# テストケース: settings の INSTALLED_APPS と Django app registry を確認する。
# 期待値: history_read_model app が登録済みで、management command discovery の対象になる。
def test_history_read_model_app_is_registered_for_django_discovery() -> None:
    settings = importlib.import_module("backend_config.settings")

    assert "history_read_model" in settings.INSTALLED_APPS
    assert apps.get_app_config("history_read_model").name == "history_read_model"


# 概要・目的: BigQuery read model package と runtime dependency が配布対象に入る契約を守る。
# テストケース: pyproject.toml の package discovery と dependencies を確認する。
# 期待値: history_read_model* が include され、google-cloud-bigquery の version range が固定される。
def test_history_read_model_package_and_bigquery_dependency_are_declared() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())

    includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    dependencies = pyproject["project"]["dependencies"]

    assert "history_read_model*" in includes
    assert "google-cloud-bigquery>=3.41,<4" in dependencies


# 概要・目的: settings import が BigQuery client 生成や
# client module import に依存しない契約を守る。
# テストケース: google.cloud.bigquery import を失敗させた状態で settings module を再読み込みする。
# 期待値: settings は BigQuery client module に触れずに読み込める。
def test_settings_import_does_not_require_bigquery_client_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import_module = importlib.import_module

    def guarded_import_module(name: str, package: str | None = None) -> object:
        if name == "google.cloud.bigquery":
            raise AssertionError("settings import must not import google.cloud.bigquery")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import_module)

    settings = importlib.reload(original_import_module("backend_config.settings"))

    assert settings.INSTALLED_APPS


# 概要・目的: 明示的に不正な secret が設定されたときに設定不足として失敗させる。
# テストケース: DJANGO_SECRET_KEY に空文字または invalid 値を設定して settings validation を呼ぶ。
# 期待値: ImproperlyConfigured が送出され、起動前に設定不備を識別できる。
@pytest.mark.parametrize("secret_key", ["", "invalid", "invalid-secret"])
def test_validate_secret_key_rejects_missing_or_invalid_values(
    monkeypatch: pytest.MonkeyPatch, secret_key: str
) -> None:
    settings = importlib.import_module("backend_config.settings")
    monkeypatch.setenv("DJANGO_SECRET_KEY", secret_key)

    with pytest.raises(ImproperlyConfigured):
        settings.validate_secret_key()


# 概要・目的: Django 標準 entrypoint が同じ settings module で
# app registry を初期化できる契約を守る。
# テストケース: manage.py、ASGI、WSGI modules を import し application object を確認する。
# 期待値: 各 module が backend_config.settings を前提に読み込め、ASGI/WSGI application を公開する。
def test_management_asgi_and_wsgi_entrypoints_load_settings() -> None:
    manage = importlib.import_module("manage")
    asgi = importlib.import_module("backend_config.asgi")
    wsgi = importlib.import_module("backend_config.wsgi")

    assert manage.DEFAULT_SETTINGS_MODULE == "backend_config.settings"
    assert asgi.application is not None
    assert wsgi.application is not None


# 概要・目的: foundation spec が対象外 API route を提供しない境界を守る。
# テストケース: 履歴同期 API と session API の path を Django URL resolver で解決する。
# 期待値: いずれも root URLconf では未定義として Resolver404 になる。
@pytest.mark.parametrize(
    "path",
    ["/api/history/sync", "/api/sessions", "/api/sessions/example-session-id"],
)
def test_foundation_does_not_register_out_of_scope_history_api_routes(path: str) -> None:
    with pytest.raises(Resolver404):
        resolve(path)

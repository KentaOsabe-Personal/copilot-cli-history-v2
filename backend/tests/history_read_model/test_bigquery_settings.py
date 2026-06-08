from pathlib import Path

import pytest

from history_read_model.bigquery_settings import (
    BigQuerySettingsError,
    load_bigquery_settings,
    read_bigquery_integration_enabled,
)


# 概要・目的: dry-run / unit mode が credentials なしで設定契約を読めることを守る。
# テストケース: 必須 env と任意 prefix を設定し、credentials を設定せずに読み込む。
# 期待値: settings object が返り、credentials_path は None になる。
def test_load_bigquery_settings_does_not_require_credentials_for_unit_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "local-project")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "copilot_history")
    monkeypatch.setenv("BIGQUERY_LOCATION", "asia-northeast1")
    monkeypatch.setenv("BIGQUERY_TABLE_PREFIX", "dev_")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    settings = load_bigquery_settings(require_credentials=False)

    assert settings.project_id == "local-project"
    assert settings.dataset_id == "copilot_history"
    assert settings.location == "asia-northeast1"
    assert settings.table_prefix == "dev_"
    assert settings.credentials_path is None


# 概要・目的: execute / compare mode が BigQuery 接続前に必須 env 不足を列挙する契約を守る。
# テストケース: 必須 env と credentials をすべて未設定にして credentials 必須 mode で読み込む。
# 期待値: BigQuerySettingsError が不足設定を保持し、BigQuery client 生成前に失敗できる。
def test_load_bigquery_settings_lists_missing_required_env_before_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET_ID",
        "BIGQUERY_LOCATION",
        "BIGQUERY_TABLE_PREFIX",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    with pytest.raises(BigQuerySettingsError) as exc_info:
        load_bigquery_settings(require_credentials=True)

    assert exc_info.value.missing_settings == (
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET_ID",
        "BIGQUERY_LOCATION",
        "credentials source (GOOGLE_APPLICATION_CREDENTIALS or ADC)",
    )


# 概要・目的: execute / compare mode が credentials path または ADC の存在を許可する契約を守る。
# テストケース: 必須 env と GOOGLE_APPLICATION_CREDENTIALS を設定して読み込む。
# 期待値: settings object が返り、credentials_path は env の path 文字列だけを保持する。
def test_load_bigquery_settings_accepts_explicit_credentials_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text("{}")
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "local-project")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "copilot_history")
    monkeypatch.setenv("BIGQUERY_LOCATION", "US")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))

    settings = load_bigquery_settings(require_credentials=True)

    assert settings.credentials_path == str(credentials_path)


# 概要・目的: credentials の内容や値を error output に含めない運用契約を守る。
# テストケース: secret らしい env 値と不正な table prefix を設定して validation error を起こす。
# 期待値: error message は key 名と理由だけを含み、secret 値は含まない。
def test_bigquery_settings_error_does_not_include_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "local-project")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "copilot_history")
    monkeypatch.setenv("BIGQUERY_LOCATION", "US")
    monkeypatch.setenv("BIGQUERY_TABLE_PREFIX", "invalid-secret-prefix!")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/super-secret-key.json")

    with pytest.raises(BigQuerySettingsError) as exc_info:
        load_bigquery_settings(require_credentials=True)

    message = str(exc_info.value)
    assert "BIGQUERY_TABLE_PREFIX" in message
    assert "invalid-secret-prefix!" not in message
    assert "/tmp/super-secret-key.json" not in message


# 概要・目的: 実 BigQuery integration validation が明示 opt-in のときだけ有効になる契約を守る。
# テストケース: BIGQUERY_READ_MODEL_INTEGRATION の未設定、false 相当、true 相当を読む。
# 期待値: "1" / "true" / "yes" / "on" だけが integration enabled として扱われる。
@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [(None, False), ("0", False), ("false", False), ("1", True), ("true", True), ("on", True)],
)
def test_read_bigquery_integration_enabled_is_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str | None,
    expected: bool,
) -> None:
    if raw_value is None:
        monkeypatch.delenv("BIGQUERY_READ_MODEL_INTEGRATION", raising=False)
    else:
        monkeypatch.setenv("BIGQUERY_READ_MODEL_INTEGRATION", raw_value)

    assert read_bigquery_integration_enabled() is expected

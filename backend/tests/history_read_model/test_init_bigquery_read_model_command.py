from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


class RecordingBigQueryClient:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.queries: list[str] = []
        self.rows = rows or []

    def query(self, sql: str) -> list[dict[str, object]]:
        self.queries.append(sql)
        return self.rows


def _set_required_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text("{}")
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "local-project")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "copilot_history")
    monkeypatch.setenv("BIGQUERY_LOCATION", "asia-northeast1")
    monkeypatch.setenv("BIGQUERY_TABLE_PREFIX", "dev_")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))


# 概要・目的: command discovery と dry-run first の初期化契約を守る。
# テストケース: 既定 option で init_bigquery_read_model を実行する。
# 期待値: BigQuery client を生成せず、target dataset / tables と作成 SQL が stdout に出る。
def test_init_bigquery_read_model_defaults_to_dry_run_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIGQUERY_PROJECT_ID", "local-project")
    monkeypatch.setenv("BIGQUERY_DATASET_ID", "copilot_history")
    monkeypatch.setenv("BIGQUERY_LOCATION", "asia-northeast1")
    monkeypatch.setenv("BIGQUERY_TABLE_PREFIX", "dev_")
    created_clients: list[object] = []
    stdout = StringIO()

    call_command(
        "init_bigquery_read_model",
        stdout=stdout,
        client_factory=lambda _settings: created_clients.append(object()),
    )

    output = stdout.getvalue()
    assert created_clients == []
    assert "Mode: dry-run" in output
    assert "Target dataset: local-project.copilot_history" in output
    assert "Target tables: dev_copilot_sessions, dev_history_sync_runs" in output
    assert "CREATE SCHEMA IF NOT EXISTS `local-project.copilot_history`" in output
    assert (
        "CREATE TABLE IF NOT EXISTS `local-project.copilot_history.dev_copilot_sessions`"
        in output
    )
    assert "Repository query/upsert: not executed by this command" in output


# 概要・目的: execute mode だけが BigQuery client を作成する契約を守る。
# テストケース: 必須 env と fake client factory を渡して --execute を実行する。
# 期待値: dataset / 2 tables の作成 SQL だけが実行され、metadata compare query は実行されない。
def test_init_bigquery_read_model_execute_runs_create_sql_with_injected_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _set_required_env(monkeypatch, tmp_path)
    client = RecordingBigQueryClient()
    stdout = StringIO()

    call_command(
        "init_bigquery_read_model",
        execute=True,
        stdout=stdout,
        client_factory=lambda _settings: client,
    )

    output = stdout.getvalue()
    assert "Mode: execute" in output
    assert "Execute result: create statements submitted" in output
    assert len(client.queries) == 3
    assert client.queries[0].startswith("CREATE SCHEMA IF NOT EXISTS")
    assert "dev_copilot_sessions" in client.queries[1]
    assert "dev_history_sync_runs" in client.queries[2]
    assert "INFORMATION_SCHEMA" not in "\n".join(client.queries)


# 概要・目的: compare mode が metadata comparator の結果を人間が識別できる形で返す契約を守る。
# テストケース: fake client が不足列と追加列を含む INFORMATION_SCHEMA 相当 rows を返す。
# 期待値: missing / incompatible は失敗扱い、extra は informational として表示される。
def test_init_bigquery_read_model_compare_reports_schema_diffs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _set_required_env(monkeypatch, tmp_path)
    client = RecordingBigQueryClient(
        rows=[
            {
                "metadata_kind": "column",
                "table_name": "dev_copilot_sessions",
                "column_name": "session_id",
                "data_type": "STRING",
                "is_nullable": "NO",
                "is_partitioning_column": "NO",
                "clustering_ordinal_position": 1,
            },
            {
                "metadata_kind": "column",
                "table_name": "dev_copilot_sessions",
                "column_name": "extra_debug_column",
                "data_type": "STRING",
                "is_nullable": "YES",
                "is_partitioning_column": "NO",
                "clustering_ordinal_position": None,
            },
            {
                "metadata_kind": "option",
                "table_name": "dev_copilot_sessions",
                "option_name": "require_partition_filter",
                "option_value": "false",
            },
        ]
    )
    stdout = StringIO()
    stderr = StringIO()

    with pytest.raises(CommandError):
        call_command(
            "init_bigquery_read_model",
            compare=True,
            stdout=stdout,
            stderr=stderr,
            client_factory=lambda _settings: client,
        )

    assert len(client.queries) == 1
    assert "INFORMATION_SCHEMA.COLUMNS" in client.queries[0]
    assert "Compare result: incompatible schema" in stderr.getvalue()
    assert "Missing:" in stderr.getvalue()
    assert "dev_copilot_sessions.source_format" in stderr.getvalue()
    assert "Incompatible:" in stderr.getvalue()
    assert "option require_partition_filter expected true but was false" in stderr.getvalue()
    assert "Extra informational:" in stdout.getvalue()
    assert "dev_copilot_sessions.extra_debug_column" in stdout.getvalue()


# 概要・目的: execute / compare mode の env validation が外部接続前に失敗する契約を守る。
# テストケース: 必須 env と credentials を未設定にして --execute を実行する。
# 期待値: client factory は呼ばれず、CommandError が不足設定 key を含む。
def test_init_bigquery_read_model_execute_validates_settings_before_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "BIGQUERY_PROJECT_ID",
        "BIGQUERY_DATASET_ID",
        "BIGQUERY_LOCATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    created_clients: list[object] = []

    with pytest.raises(CommandError) as exc_info:
        call_command(
            "init_bigquery_read_model",
            execute=True,
            client_factory=lambda _settings: created_clients.append(object()),
        )

    assert created_clients == []
    message = str(exc_info.value)
    assert "BIGQUERY_PROJECT_ID" in message
    assert "BIGQUERY_DATASET_ID" in message
    assert "BIGQUERY_LOCATION" in message
    assert "credentials source" in message

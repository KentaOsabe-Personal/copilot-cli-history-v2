from __future__ import annotations

from history_read_model import (
    BigQueryReadModelSettings,
    BigQuerySessionReadModelRepository,
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
    RepositoryExecutionOptions,
    SessionListCriteria,
    SessionReadModelRepository,
    build_copilot_session_write_input,
    plan_sync_write,
)

EXPECTED_PUBLIC_SURFACE = [
    "BigQueryReadModelSettings",
    "BigQuerySessionReadModelRepository",
    "BigQuerySettingsError",
    "CopilotSessionRow",
    "ExistingSessionMetadata",
    "FakeBigQueryReadModelRepository",
    "HistorySyncRunRow",
    "InvalidSessionWriteInput",
    "ReadModelContractError",
    "RepositoryError",
    "RepositoryErrorKind",
    "RepositoryExecutionOptions",
    "SEARCH_TEXT_VERSION",
    "SessionDetailResult",
    "SessionListCriteria",
    "SessionListResult",
    "SessionReadModelRepository",
    "SessionRowBuildCandidate",
    "SessionRowBuildStatus",
    "SyncRunLookupResult",
    "SyncRunResult",
    "SyncStatus",
    "SyncWritePlan",
    "SyncWriteResult",
    "WorkspaceOnlySessionWriteInput",
    "build_copilot_session_write_input",
    "load_bigquery_settings",
    "plan_sync_write",
    "read_bigquery_integration_enabled",
]


# 概要・目的: repository package root から後続 API / sync spec が必要な
# entrypoint を import できる契約を守る。
# テストケース: history_read_model.__all__ と代表 object の import 結果を確認する。
# 期待値: public surface が明示され、repository port / fake /
# BigQuery adapter / row builder を package から参照できる。
def test_history_read_model_package_public_surface_is_explicit() -> None:
    import history_read_model

    assert history_read_model.__all__ == EXPECTED_PUBLIC_SURFACE
    assert SessionReadModelRepository.__name__ == "SessionReadModelRepository"
    assert RepositoryExecutionOptions().__dict__ == {
        "dry_run": False,
        "maximum_bytes_billed": None,
        "location": None,
    }
    assert SessionListCriteria(from_datetime=None, to_datetime=None).limit is None
    assert FakeBigQueryReadModelRepository.__name__ == "FakeBigQueryReadModelRepository"
    assert BigQuerySessionReadModelRepository.__name__ == "BigQuerySessionReadModelRepository"
    assert BigQueryReadModelSettings.__name__ == "BigQueryReadModelSettings"
    assert CopilotSessionRow.__name__ == "CopilotSessionRow"
    assert HistorySyncRunRow.__name__ == "HistorySyncRunRow"
    assert callable(build_copilot_session_write_input)
    assert callable(plan_sync_write)

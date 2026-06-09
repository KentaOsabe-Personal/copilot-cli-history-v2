from dataclasses import replace
from datetime import UTC, datetime

from history_read_model.fake_repository import (
    CopilotSessionRow,
    FakeBigQueryReadModelRepository,
    HistorySyncRunRow,
)
from history_read_model.repository import RepositoryExecutionOptions, SessionListCriteria


def _session_row(
    session_id: str,
    *,
    created_at_source: datetime | None,
    updated_at_source: datetime | None,
    cwd: str | None = "/workspace/app",
    source_format: str = "current",
    search_text: str = "planning implementation notes",
) -> CopilotSessionRow:
    display_time = updated_at_source or created_at_source or datetime(2026, 6, 1, tzinfo=UTC)
    return CopilotSessionRow(
        session_id=session_id,
        source_format=source_format,
        source_state="complete",
        created_at_source=created_at_source,
        updated_at_source=updated_at_source,
        source_partition_date=display_time.date(),
        cwd=cwd,
        git_root="/workspace",
        repository="repo",
        branch="main",
        selected_model="gpt-5",
        event_count=1,
        message_snapshot_count=1,
        issue_count=0,
        message_count=1,
        activity_count=0,
        degraded=False,
        conversation_preview="preview",
        source_paths={"primary": f"/workspace/{session_id}.json"},
        source_fingerprint={"sha256": session_id},
        summary_payload={"id": session_id, "title": f"Summary {session_id}"},
        detail_payload={
            "id": session_id,
            "header": {"source_format": source_format},
            "messages": [{"role": "assistant", "content": session_id}],
            "conversation": {"entries": []},
            "activity": [],
            "timeline": [],
            "degraded": False,
            "issues": [],
        },
        search_text=search_text,
        search_text_version=1,
        indexed_at=datetime(2026, 6, 9, tzinfo=UTC),
    )


def _criteria(
    *,
    search_term: str | None = None,
    limit: int | None = None,
) -> SessionListCriteria:
    return SessionListCriteria(
        from_datetime=datetime(2026, 6, 1, tzinfo=UTC),
        to_datetime=datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        search_term=search_term,
        limit=limit,
    )


# 概要・目的: fake repository が一覧の表示日時 fallback と候補除外契約を守る。
# テストケース: updated_at 優先、created_at fallback、両方欠落の 3 row を保存して一覧取得する。
# 期待値: 表示日時を持つ row だけが対象になり、更新日時優先の降順で summary payload が返る。
def test_fake_repository_list_sessions_uses_display_time_and_excludes_missing_time() -> None:
    repository = FakeBigQueryReadModelRepository()
    updated = _session_row(
        "updated",
        created_at_source=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at_source=datetime(2026, 6, 8, tzinfo=UTC),
    )
    created = _session_row(
        "created",
        created_at_source=datetime(2026, 6, 7, tzinfo=UTC),
        updated_at_source=None,
    )
    missing = _session_row("missing", created_at_source=None, updated_at_source=None)
    repository.save_session(updated)
    repository.save_session(created)
    repository.save_session(missing)

    result = repository.list_sessions(_criteria(), RepositoryExecutionOptions())

    assert result.ok is True
    assert tuple(payload["id"] for payload in result.summary_payloads) == ("updated", "created")
    assert result.summary_payloads[0] is updated.summary_payload
    assert result.summary_payloads[1] is created.summary_payload


# 概要・目的: fake repository が date range と検索語を AND 条件として適用することを守る。
# テストケース: 検索語が search_text または cwd に一致する row と、日付範囲外 row を一覧取得する。
# 期待値: 検索一致かつ日付範囲内の row だけが返り、範囲外 row は除外される。
def test_fake_repository_list_sessions_filters_by_date_range_and_search_term() -> None:
    repository = FakeBigQueryReadModelRepository()
    search_text_match = _session_row(
        "search-text",
        created_at_source=datetime(2026, 6, 5, tzinfo=UTC),
        updated_at_source=None,
        search_text="contains BigQuery topic",
    )
    cwd_match = _session_row(
        "cwd",
        created_at_source=datetime(2026, 6, 4, tzinfo=UTC),
        updated_at_source=None,
        cwd="/workspace/bigquery-session-repository",
        search_text="other topic",
    )
    out_of_range = _session_row(
        "old",
        created_at_source=datetime(2026, 5, 1, tzinfo=UTC),
        updated_at_source=None,
        search_text="BigQuery topic",
    )
    repository.save_session(search_text_match)
    repository.save_session(cwd_match)
    repository.save_session(out_of_range)

    result = repository.list_sessions(
        _criteria(search_term="bigquery"),
        RepositoryExecutionOptions(),
    )

    assert result.ok is True
    assert tuple(payload["id"] for payload in result.summary_payloads) == ("search-text", "cwd")


# 概要・目的: fake repository が同一表示日時の安定順序と limit 適用順序を守る。
# テストケース: 同じ updated_at_source の 3 row を逆順に保存し、limit 2 で一覧取得する。
# 期待値: session_id 昇順に並べた後で limit が適用される。
def test_fake_repository_list_sessions_stable_ordering_before_limit() -> None:
    repository = FakeBigQueryReadModelRepository()
    timestamp = datetime(2026, 6, 8, 12, tzinfo=UTC)
    for session_id in ("c-session", "a-session", "b-session"):
        repository.save_session(
            _session_row(session_id, created_at_source=None, updated_at_source=timestamp)
        )

    result = repository.list_sessions(_criteria(limit=2), RepositoryExecutionOptions())

    assert result.ok is True
    assert tuple(payload["id"] for payload in result.summary_payloads) == (
        "a-session",
        "b-session",
    )


# 概要・目的: fake repository が不正な一覧条件を BigQuery 非依存の repository error にする。
# テストケース: date range 欠落と無効な limit を指定して list_sessions を呼ぶ。
# 期待値: missing_date_range または validation_error が返り、保存済み row は読み出されない。
def test_fake_repository_list_sessions_returns_validation_errors() -> None:
    repository = FakeBigQueryReadModelRepository()

    missing_range = repository.list_sessions(
        SessionListCriteria(from_datetime=None, to_datetime=datetime(2026, 6, 1, tzinfo=UTC)),
        RepositoryExecutionOptions(),
    )
    invalid_limit = repository.list_sessions(_criteria(limit=0), RepositoryExecutionOptions())

    assert missing_range.ok is False
    assert missing_range.error is not None
    assert missing_range.error.kind == "missing_date_range"
    assert invalid_limit.ok is False
    assert invalid_limit.error is not None
    assert invalid_limit.error.kind == "validation_error"


# 概要・目的: fake repository が detail lookup で保存済み payload を透過的に返すことを守る。
# テストケース: current と legacy の row を保存し、session_id で detail lookup する。
# 期待値: source_format にかかわらず同じ lookup 契約で、同一 detail payload object が返る。
def test_fake_repository_get_session_detail_returns_saved_payload_for_current_and_legacy() -> None:
    repository = FakeBigQueryReadModelRepository()
    current = _session_row(
        "current-session",
        created_at_source=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at_source=None,
    )
    legacy = replace(
        _session_row(
            "legacy-session",
            created_at_source=datetime(2026, 6, 2, tzinfo=UTC),
            updated_at_source=None,
            source_format="legacy",
        ),
        detail_payload={"id": "legacy-session", "header": {"source_format": "legacy"}},
    )
    repository.save_session(current)
    repository.save_session(legacy)

    current_result = repository.get_session_detail("current-session", RepositoryExecutionOptions())
    legacy_result = repository.get_session_detail("legacy-session", RepositoryExecutionOptions())

    assert current_result.ok is True
    assert current_result.found is True
    assert current_result.detail_payload is current.detail_payload
    assert legacy_result.ok is True
    assert legacy_result.found is True
    assert legacy_result.detail_payload is legacy.detail_payload


# 概要・目的: fake repository が detail lookup の not found と validation error を区別する。
# テストケース: 存在しない session_id と空白 session_id で detail lookup する。
# 期待値: 存在しない ID は success not_found、空白 ID は validation_error になる。
def test_fake_repository_get_session_detail_distinguishes_not_found_from_invalid_id() -> None:
    repository = FakeBigQueryReadModelRepository()

    missing = repository.get_session_detail("missing", RepositoryExecutionOptions())
    invalid = repository.get_session_detail("  ", RepositoryExecutionOptions())

    assert missing.ok is True
    assert missing.found is False
    assert missing.session_id == "missing"
    assert invalid.ok is False
    assert invalid.error is not None
    assert invalid.error.kind == "validation_error"


def _sync_run_row(
    sync_run_id: str,
    *,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    running_lock_key: str | None = None,
) -> HistorySyncRunRow:
    return HistorySyncRunRow(
        sync_run_id=sync_run_id,
        status=status,  # type: ignore[arg-type]
        started_at=started_at,
        finished_at=finished_at,
        started_partition_date=started_at.date(),
        processed_count=2,
        inserted_count=1,
        updated_count=1,
        saved_count=2,
        skipped_count=0,
        failed_count=0,
        degraded_count=0,
        failure_summary=None,
        degradation_summary=None,
        running_lock_key=running_lock_key,
        indexed_at=finished_at or started_at,
    )


# 概要・目的: fake repository が save_sessions を write plan に従って最新 read model へ反映する。
# テストケース: insert、update、skip、degraded row を含む保存対象を repository 契約で保存する。
# 期待値: insert/update だけが in-memory row を更新し、skip は既存 row を保持し、件数が返る。
def test_fake_repository_save_sessions_applies_insert_update_skip_and_degraded_counts() -> None:
    repository = FakeBigQueryReadModelRepository()
    existing_updated = _session_row(
        "updated",
        created_at_source=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at_source=None,
        search_text="old",
    )
    existing_skipped = _session_row(
        "skipped",
        created_at_source=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at_source=None,
    )
    repository.save_session(existing_updated)
    repository.save_session(existing_skipped)
    inserted = _session_row(
        "inserted",
        created_at_source=datetime(2026, 6, 2, tzinfo=UTC),
        updated_at_source=None,
    )
    updated = replace(
        existing_updated,
        source_fingerprint={"sha256": "new"},
        summary_payload={"id": "updated", "title": "new"},
    )
    skipped = replace(existing_skipped)
    degraded = replace(
        _session_row(
            "degraded",
            created_at_source=datetime(2026, 6, 3, tzinfo=UTC),
            updated_at_source=None,
        ),
        degraded=True,
        issue_count=1,
        detail_payload={"id": "degraded", "issues": [{"message": "partial"}]},
    )

    result = repository.save_sessions(
        (inserted, updated, skipped, degraded),
        RepositoryExecutionOptions(),
    )

    assert result.ok is True
    assert result.processed_count == 4
    assert result.inserted_count == 2
    assert result.updated_count == 1
    assert result.saved_count == 3
    assert result.skipped_count == 1
    assert result.degraded_count == 1
    assert repository.get_session("inserted") == inserted
    assert repository.get_session("updated") == updated
    assert repository.get_session("skipped") == existing_skipped
    assert repository.get_session("degraded") is degraded


# 概要・目的: fake repository の dry run が保存分類だけを返し、read model を変更しないことを守る。
# テストケース: 新規 row を dry_run で save_sessions に渡す。
# 期待値: insert 予定は返るが、session row は保存されず planned_operations が識別できる。
def test_fake_repository_save_sessions_dry_run_does_not_mutate_rows() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = _session_row(
        "dry-run",
        created_at_source=datetime(2026, 6, 2, tzinfo=UTC),
        updated_at_source=None,
    )

    result = repository.save_sessions((row,), RepositoryExecutionOptions(dry_run=True))

    assert result.ok is True
    assert result.dry_run is True
    assert result.inserted_count == 1
    assert result.planned_operations == ("metadata_lookup", "classify", "merge")
    assert repository.get_session("dry-run") is None


# 概要・目的: fake repository が sync run lifecycle を
# repository result として保存できることを守る。
# テストケース: running と terminal の sync run を保存し、running lookup を呼ぶ。
# 期待値: running lock を持つ未完了 run が found になり、terminal 保存後も running だけが返る。
def test_fake_repository_save_sync_run_and_find_running_sync_run() -> None:
    repository = FakeBigQueryReadModelRepository()
    running = _sync_run_row(
        "sync-running",
        status="running",
        started_at=datetime(2026, 6, 9, 10, tzinfo=UTC),
        running_lock_key="history-sync",
    )
    succeeded = _sync_run_row(
        "sync-succeeded",
        status="succeeded",
        started_at=datetime(2026, 6, 9, 11, tzinfo=UTC),
        finished_at=datetime(2026, 6, 9, 11, 1, tzinfo=UTC),
    )

    running_result = repository.save_sync_run(running, RepositoryExecutionOptions())
    succeeded_result = repository.save_sync_run(succeeded, RepositoryExecutionOptions())
    lookup = repository.find_running_sync_run(RepositoryExecutionOptions())

    assert running_result.ok is True
    assert running_result.sync_run_id == "sync-running"
    assert succeeded_result.ok is True
    assert lookup.ok is True
    assert lookup.found is True
    assert lookup.sync_run_id == "sync-running"
    assert repository.get_sync_run("sync-succeeded") == succeeded


# 概要・目的: fake repository が sync run dry run で lifecycle validation だけを行うことを守る。
# テストケース: valid running row を dry_run で保存する。
# 期待値: success result と planned operation は返るが、sync run は in-memory に保存されない。
def test_fake_repository_save_sync_run_dry_run_does_not_mutate_runs() -> None:
    repository = FakeBigQueryReadModelRepository()
    row = _sync_run_row(
        "sync-dry-run",
        status="running",
        started_at=datetime(2026, 6, 9, 10, tzinfo=UTC),
        running_lock_key="history-sync",
    )

    result = repository.save_sync_run(row, RepositoryExecutionOptions(dry_run=True))

    assert result.ok is True
    assert result.dry_run is True
    assert result.planned_operations == ("validate_sync_run",)
    assert repository.get_sync_run("sync-dry-run") is None


# 概要・目的: fake repository の running lookup dry run が
# 実 state を読まず予定として返ることを守る。
# テストケース: running row が存在する状態で dry_run の find_running_sync_run を呼ぶ。
# 期待値: mutation や state read result ではなく not_found の dry-run plan として識別できる。
def test_fake_repository_find_running_sync_run_dry_run_returns_plan_only() -> None:
    repository = FakeBigQueryReadModelRepository()
    repository.save_sync_run(
        _sync_run_row(
            "sync-running",
            status="running",
            started_at=datetime(2026, 6, 9, 10, tzinfo=UTC),
            running_lock_key="history-sync",
        )
    )

    result = repository.find_running_sync_run(RepositoryExecutionOptions(dry_run=True))

    assert result.ok is True
    assert result.found is False
    assert result.dry_run is True
    assert result.planned_operations == ("running_sync_lookup",)

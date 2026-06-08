from datetime import UTC, datetime
from pathlib import Path

import pytest

from copilot_history.current_reader import CurrentSessionReader
from copilot_history.source_catalog import SourceCatalog
from copilot_history.types import ResolvedHistoryRoot, SessionSource

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _source_for_fixture(fixture_name: str) -> SessionSource:
    root = FIXTURE_ROOT / fixture_name
    sources = SourceCatalog().list_sources(
        ResolvedHistoryRoot(
            requested_root=str(root),
            current_root=str(root / "session-state"),
            legacy_root=str(root / "history-session-state"),
        )
    )
    return sources[0]


# 概要・目的: current workspace metadata を normalized session contract へ対応付ける。
# テストケース: workspace.yaml と events.jsonl を持つ current_valid fixture を読む。
# 期待値: session id、作業ディレクトリ、repository context、source paths が保持される。
def test_current_reader_maps_workspace_metadata_to_normalized_session() -> None:
    session = CurrentSessionReader().read(_source_for_fixture("current_valid"))

    assert session.session_id == "current-valid"
    assert session.source_format == "current"
    assert session.source_state == "degraded"
    assert session.cwd == "/workspace/current"
    assert session.repository == "copilot-cli-history-v2"
    assert session.branch == "main"
    assert session.git_root is None
    assert session.source_paths["workspace"].endswith("/workspace.yaml")
    assert session.source_paths["events"].endswith("/events.jsonl")


# 概要・目的: events がない current session でも workspace 由来の session を返す。
# テストケース: current_workspace_only fixture を CurrentSessionReader で読む。
# 期待値: workspace_only state、空 events、current.events_missing warning が返る。
def test_current_reader_returns_workspace_only_session_when_events_are_missing() -> None:
    session = CurrentSessionReader().read(_source_for_fixture("current_workspace_only"))

    assert session.source_state == "workspace_only"
    assert session.events == ()
    assert session.issues[0].code == "current.events_missing"
    assert session.issues[0].severity == "warning"


# 概要・目的: workspace.yaml の欠損や parse failure を session issue として扱う。
# テストケース: invalid YAML fixture を CurrentSessionReader で読む。
# 期待値: root failure ではなく degraded session と current.workspace_parse_failed issue が返る。
def test_current_reader_marks_invalid_workspace_as_degraded_session() -> None:
    session = CurrentSessionReader().read(_source_for_fixture("current_invalid_workspace"))

    assert session.session_id == "current-invalid-workspace"
    assert session.source_state == "degraded"
    assert session.cwd is None
    assert session.issues[0].code == "current.workspace_parse_failed"
    assert session.issues[0].severity == "error"


# 概要・目的: events JSONL の壊れた行を issue 化し、読める event は保持する。
# テストケース: invalid JSONL fixture を CurrentSessionReader で読む。
# 期待値: current.event_parse_failed issue が line sequence と source path 付きで返る。
def test_current_reader_reports_invalid_jsonl_line_without_dropping_session() -> None:
    session = CurrentSessionReader().read(_source_for_fixture("current_invalid_events"))

    assert session.source_state == "degraded"
    assert session.events == ()
    assert session.issues[0].code == "current.event_parse_failed"
    assert session.issues[0].sequence == 1
    assert session.issues[0].source_path is not None
    assert session.issues[0].source_path.endswith("/events.jsonl")


# 概要・目的: event order と selected model 優先順位を current reader で固定する。
# テストケース: model 候補を含む events.jsonl を一時 root に作成して読む。
# 期待値: source order の sequence が保持され、同優先度は後勝ちで selected_model が決まる。
def test_current_reader_preserves_event_order_and_selects_model_by_priority(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session-state" / "current-models"
    session_dir.mkdir(parents=True)
    (session_dir / "workspace.yaml").write_text(
        "\n".join(
            [
                "session_id: current-models",
                "cwd: /workspace/models",
                "created_at: '2026-06-08T01:00:00Z'",
                "updated_at: '2026-06-08T01:05:00Z'",
            ]
        ),
        encoding="utf-8",
    )
    (session_dir / "events.jsonl").write_text(
        "\n".join(
            [
                '{"type":"assistant.usage","data":{"model":"gpt-low"},"timestamp":"2026-06-08T01:01:00Z"}',
                '{"type":"tool.execution_complete","data":{"model":"gpt-tool"},"timestamp":"2026-06-08T01:02:00Z"}',
                '{"type":"tool.execution_complete","data":{"model":"gpt-tool-later"},"timestamp":"2026-06-08T01:03:00Z"}',
                '{"type":"session.shutdown","data":{"currentModel":"gpt-final"},"timestamp":"2026-06-08T01:04:00Z"}',
            ]
        ),
        encoding="utf-8",
    )
    source = SourceCatalog().list_sources(
        ResolvedHistoryRoot(
            requested_root=str(tmp_path),
            current_root=str(tmp_path / "session-state"),
            legacy_root=str(tmp_path / "history-session-state"),
        )
    )[0]

    session = CurrentSessionReader().read(source)

    assert [event.sequence for event in session.events] == [1, 2, 3, 4]
    assert session.selected_model == "gpt-final"
    assert session.updated_at == datetime(2026, 6, 8, 1, 4, tzinfo=UTC)
    assert [issue.code for issue in session.issues] == [
        "event.unknown_shape",
        "event.unknown_shape",
    ]


# 概要・目的: current reader が current source 以外を受け付けない境界を守る。
# テストケース: legacy source_format の SessionSource を CurrentSessionReader に渡す。
# 期待値: ValueError により format boundary violation を検出する。
def test_current_reader_rejects_non_current_source() -> None:
    source = SessionSource(
        session_id="legacy",
        source_format="legacy",
        source_path="/tmp/legacy.json",
        artifact_paths={"legacy_json": "/tmp/legacy.json"},
    )

    with pytest.raises(ValueError, match="current"):
        CurrentSessionReader().read(source)

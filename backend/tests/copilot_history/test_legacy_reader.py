from pathlib import Path

import pytest

from copilot_history.legacy_reader import LegacySessionReader
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


# 概要・目的: legacy JSON を current と同じ normalized session contract へ対応付ける。
# テストケース: legacy_valid fixture を LegacySessionReader で読む。
# 期待値: session id、selected model、timeline event が保持される。
def test_legacy_reader_maps_json_session_to_normalized_session() -> None:
    session = LegacySessionReader().read(_source_for_fixture("legacy_valid"))

    assert session.session_id == "legacy-valid"
    assert session.source_format == "legacy"
    assert session.source_state == "degraded"
    assert session.selected_model == "gpt-5"
    assert session.cwd is None
    assert session.events[0].kind == "message"
    assert session.events[0].content == "legacy message"
    assert session.issues[0].code == "event.partial_mapping"


# 概要・目的: legacy の timeline と chatMessages から event と message snapshot を作る。
# テストケース: timeline と chatMessages を含む legacy JSON を一時 root に作成して読む。
# 期待値: event sequence、message snapshot sequence、raw payload が追跡可能な形で返る。
def test_legacy_reader_maps_timeline_and_message_snapshots(tmp_path: Path) -> None:
    legacy_root = tmp_path / "history-session-state"
    legacy_root.mkdir()
    legacy_file = legacy_root / "legacy-rich.json"
    legacy_file.write_text(
        """
        {
          "sessionId": "legacy-rich",
          "startTime": "2026-06-08T02:00:00Z",
          "selectedModel": "gpt-legacy",
          "timeline": [
            {
              "type": "user_message",
              "role": "user",
              "content": "hello",
              "timestamp": "2026-06-08T02:01:00Z"
            },
            "unexpected"
          ],
          "chatMessages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer"}
          ]
        }
        """,
        encoding="utf-8",
    )
    source = SourceCatalog().list_sources(
        ResolvedHistoryRoot(
            requested_root=str(tmp_path),
            current_root=str(tmp_path / "session-state"),
            legacy_root=str(legacy_root),
        )
    )[0]

    session = LegacySessionReader().read(source)

    assert session.session_id == "legacy-rich"
    assert session.created_at is not None
    assert [event.sequence for event in session.events] == [1, 2]
    assert session.events[1].kind == "unknown"
    assert [snapshot.sequence for snapshot in session.message_snapshots] == [1, 2]
    assert session.message_snapshots[1].role == "assistant"
    assert session.message_snapshots[1].content == "answer"
    assert session.issues[0].code == "event.unknown_shape"


# 概要・目的: legacy JSON の parse failure を対象 session の issue として扱う。
# テストケース: invalid JSON fixture を LegacySessionReader で読む。
# 期待値: file stem の session id、degraded state、legacy.json_parse_failed issue が返る。
def test_legacy_reader_marks_invalid_json_as_degraded_session() -> None:
    session = LegacySessionReader().read(_source_for_fixture("legacy_invalid"))

    assert session.session_id == "legacy-invalid"
    assert session.source_state == "degraded"
    assert session.events == ()
    assert session.message_snapshots == ()
    assert session.issues[0].code == "legacy.json_parse_failed"
    assert session.issues[0].severity == "error"


# 概要・目的: legacy source file が読めない場合も root failure ではなく session issue にする。
# テストケース: 存在しない legacy_json artifact path を LegacySessionReader に渡す。
# 期待値: legacy.source_unreadable issue を持つ degraded session が返る。
def test_legacy_reader_returns_session_issue_for_unreadable_source() -> None:
    source = SessionSource(
        session_id="missing",
        source_format="legacy",
        source_path="/tmp/missing.json",
        artifact_paths={"legacy_json": "/tmp/missing.json"},
    )

    session = LegacySessionReader().read(source)

    assert session.session_id == "missing"
    assert session.source_state == "degraded"
    assert session.issues[0].code == "legacy.source_unreadable"


# 概要・目的: legacy reader が legacy source 以外を受け付けない境界を守る。
# テストケース: current source_format の SessionSource を LegacySessionReader に渡す。
# 期待値: ValueError により format boundary violation を検出する。
def test_legacy_reader_rejects_non_legacy_source() -> None:
    source = SessionSource(
        session_id="current",
        source_format="current",
        source_path="/tmp/current",
        artifact_paths={"workspace": "/tmp/workspace.yaml", "events": "/tmp/events.jsonl"},
    )

    with pytest.raises(ValueError, match="legacy"):
        LegacySessionReader().read(source)

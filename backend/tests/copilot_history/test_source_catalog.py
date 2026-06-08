from pathlib import Path
from typing import cast

import pytest

from copilot_history.root_resolver import RootResolver
from copilot_history.source_catalog import SourceCatalog
from copilot_history.types import ReadFailureResult, ResolvedHistoryRoot

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


# 概要・目的: 明示 root が local filesystem の履歴 root として解決される契約を守る。
# テストケース: mixed_root fixture を明示 root として RootResolver に渡す。
# 期待値: current / legacy の候補 root が session-state / history-session-state を指す。
def test_root_resolver_resolves_explicit_history_root() -> None:
    root = FIXTURE_ROOT / "mixed_root"

    resolved = RootResolver().resolve(root)

    assert isinstance(resolved, ResolvedHistoryRoot)
    assert resolved.requested_root == str(root)
    assert resolved.current_root == str(root / "session-state")
    assert resolved.legacy_root == str(root / "history-session-state")


# 概要・目的: 明示 root 未指定時に COPILOT_HOME を履歴 root 候補として使う契約を守る。
# テストケース: COPILOT_HOME に mixed_root fixture を設定して RootResolver を呼ぶ。
# 期待値: fallback root ではなく COPILOT_HOME 配下の current / legacy root が返る。
def test_root_resolver_uses_copilot_home_when_root_is_not_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FIXTURE_ROOT / "mixed_root"
    monkeypatch.setenv("COPILOT_HOME", str(root))

    resolved = RootResolver().resolve()

    assert isinstance(resolved, ResolvedHistoryRoot)
    assert resolved.requested_root == str(root)
    assert resolved.current_root == str(root / "session-state")
    assert resolved.legacy_root == str(root / "history-session-state")


# 概要・目的: 履歴 root 全体の欠損は session degraded ではなく fatal failure として扱う。
# テストケース: 存在しない directory を RootResolver に渡す。
# 期待値: root_missing の ReadFailureResult が返り、session 情報は含まれない。
def test_root_resolver_returns_root_failure_for_missing_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"

    failure = RootResolver().resolve(missing_root)

    assert isinstance(failure, ReadFailureResult)
    assert failure.code == "root_missing"
    assert failure.root_path == str(missing_root)
    assert not hasattr(failure, "sessions")


# 概要・目的: directory として扱えない root を session issue と混同しない。
# テストケース: 通常 file を履歴 root として RootResolver に渡す。
# 期待値: root_unreadable の fatal failure が返る。
def test_root_resolver_returns_root_failure_for_non_directory_root(tmp_path: Path) -> None:
    file_root = tmp_path / "copilot-home"
    file_root.write_text("not a directory", encoding="utf-8")

    failure = RootResolver().resolve(file_root)

    assert isinstance(failure, ReadFailureResult)
    assert failure.code == "root_unreadable"
    assert "directory" in failure.message


# 概要・目的: 参照権限のない root を local root failure として分類する。
# テストケース: read / execute permission を落とした directory を RootResolver に渡す。
# 期待値: root_permission_denied の fatal failure が返る。
def test_root_resolver_returns_root_failure_for_unreadable_root(tmp_path: Path) -> None:
    unreadable_root = tmp_path / "unreadable"
    unreadable_root.mkdir()
    unreadable_root.chmod(0)

    try:
        failure = RootResolver().resolve(unreadable_root)
    finally:
        unreadable_root.chmod(0o700)

    assert isinstance(failure, ReadFailureResult)
    assert failure.code == "root_permission_denied"


# 概要・目的: current / legacy が共存する root から両形式の source を列挙する。
# テストケース: mixed_root fixture の ResolvedHistoryRoot を SourceCatalog に渡す。
# 期待値: current と legacy が deterministic order で同じ一覧に含まれ、
# raw file location と artifact path が後続 reader から識別できる。
def test_source_catalog_lists_current_and_legacy_sources_in_deterministic_order() -> None:
    root = FIXTURE_ROOT / "mixed_root"
    resolved = ResolvedHistoryRoot(
        requested_root=str(root),
        current_root=str(root / "session-state"),
        legacy_root=str(root / "history-session-state"),
    )

    sources = SourceCatalog().list_sources(resolved)

    assert [source.session_id for source in sources] == ["current-mixed", "legacy-mixed"]
    current_source = sources[0]
    legacy_source = sources[1]
    assert current_source.source_format == "current"
    assert current_source.source_path == str(root / "session-state" / "current-mixed")
    assert current_source.artifact_paths == {
        "workspace": str(root / "session-state" / "current-mixed" / "workspace.yaml"),
        "events": str(root / "session-state" / "current-mixed" / "events.jsonl"),
    }
    assert legacy_source.source_format == "legacy"
    assert legacy_source.source_path == str(root / "history-session-state" / "legacy-mixed.json")
    assert legacy_source.artifact_paths == {
        "legacy_json": str(root / "history-session-state" / "legacy-mixed.json")
    }


# 概要・目的: source discovery が file content parse を行わず file stem fallback を守る。
# テストケース: sessionId と file stem が異なる legacy JSON を SourceCatalog に渡す。
# 期待値: JSON 内容ではなく file stem が session id として使われる。
def test_source_catalog_uses_legacy_file_stem_without_parsing_payload(tmp_path: Path) -> None:
    legacy_root = tmp_path / "history-session-state"
    legacy_root.mkdir()
    legacy_file = legacy_root / "stem-id.json"
    legacy_file.write_text('{"sessionId":"payload-id"}', encoding="utf-8")
    resolved = ResolvedHistoryRoot(
        requested_root=str(tmp_path),
        current_root=str(tmp_path / "session-state"),
        legacy_root=str(legacy_root),
    )

    sources = SourceCatalog().list_sources(resolved)

    assert len(sources) == 1
    assert sources[0].session_id == "stem-id"


# 概要・目的: source descriptor の mapping fields が discovery 後に変更されない契約を守る。
# テストケース: current source の artifact_paths を mutable mapping として変更しようとする。
# 期待値: read-only mapping により TypeError が発生する。
def test_session_source_freezes_artifact_paths() -> None:
    root = FIXTURE_ROOT / "current_valid"
    resolved = ResolvedHistoryRoot(
        requested_root=str(root),
        current_root=str(root / "session-state"),
        legacy_root=str(root / "history-session-state"),
    )
    source = SourceCatalog().list_sources(resolved)[0]

    artifact_paths = cast(dict[str, str], source.artifact_paths)

    try:
        artifact_paths["workspace"] = "/tmp/changed"
    except TypeError as exc:
        assert "mappingproxy" in str(exc)
    else:
        raise AssertionError("artifact_paths must be read-only")

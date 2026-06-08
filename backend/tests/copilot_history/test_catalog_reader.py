from pathlib import Path

from copilot_history.catalog_reader import SessionCatalogReader
from copilot_history.types import ReadFailureResult, ReadSuccessResult

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


# 概要・目的: catalog reader が履歴 root 全体の失敗を session degraded と混同しない。
# テストケース: 存在しない root を SessionCatalogReader に渡す。
# 期待値: source 列挙や reader 呼び出しに進まず ReadFailureResult が返る。
def test_catalog_reader_returns_root_failure_without_reading_sources(tmp_path: Path) -> None:
    result = SessionCatalogReader().read(tmp_path / "missing-root")

    assert isinstance(result, ReadFailureResult)
    assert result.code == "root_missing"
    assert not hasattr(result, "sessions")


# 概要・目的: current / legacy session を同じ success result branch で返す。
# テストケース: mixed_root fixture を SessionCatalogReader で読む。
# 期待値: current と legacy の normalized session が deterministic order で sessions に含まれる。
def test_catalog_reader_reads_current_and_legacy_sessions_from_mixed_root() -> None:
    result = SessionCatalogReader().read(FIXTURE_ROOT / "mixed_root")

    assert isinstance(result, ReadSuccessResult)
    assert [session.session_id for session in result.sessions] == [
        "current-mixed",
        "legacy-mixed",
    ]
    assert [session.source_format for session in result.sessions] == ["current", "legacy"]
    assert result.sessions[0].events[0].content == "mixed current"


# 概要・目的: 個別 session の degraded issue を root failure へ昇格させない。
# テストケース: invalid current と valid legacy が共存する一時 root を catalog reader で読む。
# 期待値: success result の中で両 session が返り、壊れた current だけに issue が残る。
def test_catalog_reader_keeps_reading_other_sessions_when_one_session_is_degraded(
    tmp_path: Path,
) -> None:
    current_dir = tmp_path / "session-state" / "broken-current"
    current_dir.mkdir(parents=True)
    (current_dir / "workspace.yaml").write_text(":", encoding="utf-8")
    legacy_root = tmp_path / "history-session-state"
    legacy_root.mkdir()
    (legacy_root / "good-legacy.json").write_text(
        '{"sessionId":"good-legacy","timeline":[]}',
        encoding="utf-8",
    )

    result = SessionCatalogReader().read(tmp_path)

    assert isinstance(result, ReadSuccessResult)
    assert [session.session_id for session in result.sessions] == [
        "broken-current",
        "good-legacy",
    ]
    assert result.sessions[0].source_state == "degraded"
    assert result.sessions[0].issues[0].code == "current.workspace_parse_failed"
    assert result.sessions[1].source_state == "complete"

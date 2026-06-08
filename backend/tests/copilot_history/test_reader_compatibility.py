import json
from pathlib import Path

from copilot_history.catalog_reader import SessionCatalogReader
from copilot_history.projections import (
    ActivityProjector,
    ConversationProjector,
    SearchTextProjector,
)
from copilot_history.types import ReadSuccessResult

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _reader_contract_snapshot(root_name: str) -> dict[str, object]:
    result = SessionCatalogReader().read(FIXTURE_ROOT / root_name)
    assert isinstance(result, ReadSuccessResult)

    conversation_projector = ConversationProjector()
    activity_projector = ActivityProjector()
    search_text_projector = SearchTextProjector(conversation_projector)
    snapshot: dict[str, object] = {}
    for session in result.sessions:
        conversation = conversation_projector.project(session)
        activity = activity_projector.project(session)
        search_text = search_text_projector.project(session)
        snapshot[session.session_id] = {
            "activity": [
                {
                    "body": entry.body,
                    "category": entry.category,
                    "sequence": entry.sequence,
                }
                for entry in activity.entries
            ],
            "conversation": [
                {
                    "content": entry.content,
                    "role": entry.role,
                    "sequence": entry.sequence,
                }
                for entry in conversation.entries
            ],
            "issues": [
                {
                    "code": issue.code,
                    "sequence": issue.sequence,
                    "severity": issue.severity,
                }
                for issue in session.issues
            ],
            "search_parts": list(search_text.parts),
            "selected_model": session.selected_model,
            "source_format": session.source_format,
            "source_state": session.source_state,
        }
    return snapshot


# 概要・目的: Rails/API contract fixture 由来の current / legacy 互換期待値を固定する。
# テストケース: mixed_root fixture を reader で読み、
# session と projection の代表 shape を JSON fixture と比較する。
# 期待値: normalized session、conversation、activity、issue、search text source が
# 後続 spec の入力として安定する。
def test_reader_outputs_representative_contract_fixture_for_current_and_legacy() -> None:
    expected_path = FIXTURE_ROOT / "api_contract_compatibility" / "expected_reader_contract.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    assert _reader_contract_snapshot("mixed_root") == expected

from datetime import UTC, datetime

from copilot_history.event_normalizer import EventNormalizer


# 概要・目的: current / legacy の既知 message event を同じ normalized contract に写像する。
# テストケース: dotted current message と legacy-compatible message を EventNormalizer に渡す。
# 期待値: role、content、timestamp、raw payload が保持された message event が issue なしで返る。
def test_event_normalizer_maps_known_current_and_legacy_messages() -> None:
    normalizer = EventNormalizer()

    current_result = normalizer.normalize(
        {
            "type": "assistant.message",
            "data": {"content": "current response"},
            "timestamp": "2026-04-28T01:00:04Z",
        },
        source_format="current",
        sequence=1,
        source_path="/tmp/events.jsonl",
    )
    legacy_result = normalizer.normalize(
        {
            "type": "user_message",
            "role": "user",
            "content": "legacy prompt",
            "timestamp": "2026-04-26T09:00:01Z",
        },
        source_format="legacy",
        sequence=2,
        source_path="/tmp/legacy.json",
    )

    assert current_result.event.kind == "message"
    assert current_result.event.mapping_status == "complete"
    assert current_result.event.raw_type == "assistant.message"
    assert current_result.event.role == "assistant"
    assert current_result.event.content == "current response"
    assert current_result.event.occurred_at == datetime(2026, 4, 28, 1, 0, 4, tzinfo=UTC)
    assert current_result.issues == ()
    assert legacy_result.event.kind == "message"
    assert legacy_result.event.role == "user"
    assert legacy_result.event.content == "legacy prompt"
    assert legacy_result.event.occurred_at == datetime(2026, 4, 26, 9, 0, 1, tzinfo=UTC)
    assert legacy_result.issues == ()


# 概要・目的: assistant turn、tool execution、hook、skill を conversation と区別できる activity
#   基礎情報として保持する。
# テストケース: current の detail 系 event をそれぞれ EventNormalizer に渡す。
# 期待値: detail.category と detail.body が Rails 互換 rule で補完される。
def test_event_normalizer_maps_current_detail_events() -> None:
    normalizer = EventNormalizer()

    cases: list[tuple[dict[str, object], str, str | None]] = [
        (
            {"type": "assistant.turn_started", "data": {"turnId": "turn-1"}},
            "assistant_turn",
            "turn-1",
        ),
        (
            {
                "type": "tool.execution_complete",
                "data": {"toolName": "functions.exec", "toolCallId": "call-1"},
            },
            "tool_execution",
            "functions.exec / call-1",
        ),
        (
            {"type": "hook.start", "data": {"hookEventName": "before-tool", "matcher": "*"}},
            "hook",
            "before-tool / *",
        ),
        (
            {"type": "skill.invoked", "data": {"skillName": "kiro-review", "toolName": "skill"}},
            "skill",
            "kiro-review / skill",
        ),
    ]

    for sequence, (raw_event, category, body) in enumerate(cases, start=1):
        result = normalizer.normalize(
            {**raw_event, "timestamp": "2026-04-28T02:00:03Z"},
            source_format="current",
            sequence=sequence,
            source_path="/tmp/events.jsonl",
        )

        assert result.event.kind == "detail"
        assert result.event.mapping_status == "complete"
        assert result.event.detail == {
            "category": category,
            "title": raw_event["type"],
            "body": body,
        }
        assert result.issues == ()


# 概要・目的: 未知 shape でも raw payload を失わず degraded issue と同時に返す。
# テストケース: current の未対応 event と非 mapping payload を EventNormalizer に渡す。
# 期待値: unknown event と event.unknown_shape warning が返り、
# source path と sequence が保持される。
def test_event_normalizer_preserves_unknown_event_payloads() -> None:
    normalizer = EventNormalizer()

    result = normalizer.normalize(
        {"type": "mystery.event", "data": {"value": 42}, "timestamp": "2026-04-28T02:00:04Z"},
        source_format="current",
        sequence=4,
        source_path="/tmp/events.jsonl",
    )
    non_mapping_result = normalizer.normalize(
        ["unexpected", {"value": 42}],
        source_format="legacy",
        sequence=5,
        source_path="/tmp/legacy.json",
    )

    assert result.event.kind == "unknown"
    assert result.event.mapping_status == "complete"
    assert result.event.raw_payload == {
        "type": "mystery.event",
        "data": {"value": 42},
        "timestamp": "2026-04-28T02:00:04Z",
    }
    assert result.issues[0].code == "event.unknown_shape"
    assert result.issues[0].source_path == "/tmp/events.jsonl"
    assert result.issues[0].sequence == 4
    assert non_mapping_result.event.kind == "unknown"
    assert non_mapping_result.event.raw_type == "list"
    assert non_mapping_result.event.raw_payload == {"value": ["unexpected", {"value": 42}]}
    assert non_mapping_result.issues[0].code == "event.unknown_shape"


# 概要・目的: 属性不足や壊れた tool request を partial mapping として追跡する。
# テストケース: timestamp 欠損の legacy message と
# name 欠損 tool request を含む current message を渡す。
# 期待値: 読めた role / content / tool call は保持され、event.partial_mapping warning が返る。
def test_event_normalizer_returns_partial_event_with_issue() -> None:
    normalizer = EventNormalizer()

    legacy_result = normalizer.normalize(
        {"type": "assistant_message", "role": "assistant", "content": "partial response"},
        source_format="legacy",
        sequence=3,
        source_path="/tmp/legacy.json",
    )
    current_result = normalizer.normalize(
        {
            "type": "assistant.message",
            "data": {"content": "uses a tool", "toolRequests": [{"arguments": {"command": "pwd"}}]},
            "timestamp": "2026-04-28T03:00:04Z",
        },
        source_format="current",
        sequence=4,
        source_path="/tmp/events.jsonl",
    )

    assert legacy_result.event.mapping_status == "partial"
    assert legacy_result.event.role == "assistant"
    assert legacy_result.event.content == "partial response"
    assert legacy_result.issues[0].code == "event.partial_mapping"
    assert legacy_result.issues[0].severity == "warning"
    assert current_result.event.mapping_status == "partial"
    assert current_result.event.tool_calls[0].name is None
    assert current_result.event.tool_calls[0].arguments_preview == '{"command":"pwd"}'
    assert current_result.issues[0].code == "event.partial_mapping"


# 概要・目的: tool call arguments の秘匿 key redaction と
# preview truncation の互換性を守る。
# テストケース: token と nested password を含む長い arguments を
# current assistant message に含める。
# 期待値: secret 系値は再帰的に redacted され、240 文字 preview と truncate flag が返る。
def test_event_normalizer_redacts_and_truncates_tool_call_arguments() -> None:
    normalizer = EventNormalizer()

    result = normalizer.normalize(
        {
            "type": "assistant.message",
            "data": {
                "content": "I can summarize the request.",
                "toolRequests": [
                    {
                        "name": "functions.exec",
                        "arguments": {
                            "command": "printenv",
                            "token": "super-secret-token",
                            "nested": {"password": "not-for-output"},
                            "description": "x" * 400,
                        },
                    }
                ],
            },
            "timestamp": "2026-04-28T03:00:04Z",
        },
        source_format="current",
        sequence=6,
        source_path="/tmp/events.jsonl",
    )

    tool_call = result.event.tool_calls[0]
    assert result.event.mapping_status == "complete"
    assert tool_call.name == "functions.exec"
    assert tool_call.arguments_preview is not None
    assert '"token":"[REDACTED]"' in tool_call.arguments_preview
    assert '"password":"[REDACTED]"' in tool_call.arguments_preview
    assert "super-secret-token" not in tool_call.arguments_preview
    assert "not-for-output" not in tool_call.arguments_preview
    assert len(tool_call.arguments_preview) == 240
    assert tool_call.is_truncated is True
    assert result.issues == ()


# 概要・目的: source order の sequence を normalizer が変更しない契約を守る。
# テストケース: sequence=12 の known event を EventNormalizer に渡す。
# 期待値: NormalizedEvent.sequence が reader から渡された値のまま返る。
def test_event_normalizer_preserves_source_sequence() -> None:
    result = EventNormalizer().normalize(
        {
            "type": "system.message",
            "data": {"content": "system"},
            "timestamp": "2026-04-28T04:00:04Z",
        },
        source_format="current",
        sequence=12,
        source_path="/tmp/events.jsonl",
    )

    assert result.event.sequence == 12

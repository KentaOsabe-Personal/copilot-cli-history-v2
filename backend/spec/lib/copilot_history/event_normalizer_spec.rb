require "rails_helper"

RSpec.describe CopilotHistory::EventNormalizer do
  describe "#call" do
    let(:source_path) { Pathname("/tmp/copilot-history/events.jsonl") }
    subject(:normalizer) { described_class.new(source_path: source_path) }

    shared_examples "a known normalized message" do |source_format|
      # 概要・目的: 「normalizes a known #{source_format} message event without emitting issues」を通じて、reader と
      #   fixture の読取・劣化時の扱いを検証する。
      # テストケース: 「normalizes a known #{source_format} message event without emitting issues」の条件・入力・操作を実行する。
      # 期待値: a known #{source_format} message event without emitting issues が正規化されること。
      it "normalizes a known #{source_format} message event without emitting issues" do
        result = normalizer.call(
          raw_event: {
            "type" => "user_message",
            "role" => "user",
            "content" => "show recent sessions",
            "timestamp" => "2026-04-26T09:00:01Z"
          },
          source_format: source_format,
          sequence: 1
        )

        expect(result).to eq(
          CopilotHistory::Types::NormalizationResult.new(
            event: CopilotHistory::Types::NormalizedEvent.new(
              sequence: 1,
              kind: :message,
              mapping_status: :complete,
              raw_type: "user_message",
              occurred_at: "2026-04-26T09:00:01Z",
              role: "user",
              content: "show recent sessions",
              tool_calls: [],
              detail: nil,
              raw_payload: {
                "type" => "user_message",
                "role" => "user",
                "content" => "show recent sessions",
                "timestamp" => "2026-04-26T09:00:01Z"
              }
            ),
            issues: []
          )
        )
      end
    end

    shared_examples "a partially normalized message" do |source_format|
      # 概要・目的: 「returns a partial #{source_format} event with a compatibility warning when a known message
      #   shape is incomplete」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
      # テストケース: 「returns a partial #{source_format} event with a compatibility warning when a known message
      #   shape is incomplete」の条件・入力・操作を実行する。
      # 期待値: a partial #{source_format} event with a compatibility warning when a known message shape is
      #   incomplete を返すこと。
      it "returns a partial #{source_format} event with a compatibility warning when a known message shape is incomplete" do
        result = normalizer.call(
          raw_event: {
            "type" => "assistant_message",
            "role" => "assistant",
            "content" => "partial response"
          },
          source_format: source_format,
          sequence: 4
        )

        expect(result.event).to eq(
          CopilotHistory::Types::NormalizedEvent.new(
            sequence: 4,
            kind: :message,
            mapping_status: :partial,
            raw_type: "assistant_message",
            occurred_at: nil,
            role: "assistant",
            content: "partial response",
            tool_calls: [],
            detail: nil,
            raw_payload: {
              "type" => "assistant_message",
              "role" => "assistant",
              "content" => "partial response"
            }
          )
        )
        expect(result.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
              message: "event payload matched partially",
              source_path: source_path,
              sequence: 4,
              severity: :warning
            )
          ]
        )
      end
    end

    shared_examples "an unknown normalized event" do |source_format|
      # 概要・目的: 「returns an unknown #{source_format} event and preserves the raw payload for unsupported
      #   shapes」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
      # テストケース: 「returns an unknown #{source_format} event and preserves the raw payload for unsupported
      #   shapes」の条件・入力・操作を実行する。
      # 期待値: an unknown #{source_format} event and preserves the raw payload for unsupported shapes を返すこと。
      it "returns an unknown #{source_format} event and preserves the raw payload for unsupported shapes" do
        result = normalizer.call(
          raw_event: {
            "type" => "mystery-event",
            "payload" => { "value" => 42 },
            "timestamp" => "2026-04-26T09:00:03Z"
          },
          source_format: source_format,
          sequence: 9
        )

        expect(result.event).to eq(
          CopilotHistory::Types::NormalizedEvent.new(
            sequence: 9,
            kind: :unknown,
            mapping_status: :complete,
            raw_type: "mystery-event",
            occurred_at: "2026-04-26T09:00:03Z",
            role: nil,
            content: nil,
            tool_calls: [],
            detail: nil,
            raw_payload: {
              "type" => "mystery-event",
              "payload" => { "value" => 42 },
              "timestamp" => "2026-04-26T09:00:03Z"
            }
          )
        )
        expect(result.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
              message: "event payload could not be mapped to canonical fields",
              source_path: source_path,
              sequence: 9,
              severity: :warning
            )
          ]
        )
      end
    end

    # 概要・目的: 「treats non-hash payloads as unknown events without raising」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「treats non-hash payloads as unknown events without raising」の条件・入力・操作を実行する。
    # 期待値: non-hash payloads が unknown events without raising として扱われること。
    it "treats non-hash payloads as unknown events without raising" do
      result = normalizer.call(
        raw_event: [ "unexpected", { "value" => 42 } ],
        source_format: :current,
        sequence: 11
      )

      expect(result.event).to eq(
        CopilotHistory::Types::NormalizedEvent.new(
          sequence: 11,
          kind: :unknown,
          mapping_status: :complete,
          raw_type: "array",
          occurred_at: nil,
          role: nil,
          content: nil,
          tool_calls: [],
          detail: nil,
          raw_payload: [ "unexpected", { "value" => 42 } ]
        )
      )
      expect(result.issues).to eq(
        [
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
            message: "event payload could not be mapped to canonical fields",
            source_path: source_path,
            sequence: 11,
            severity: :warning
          )
        ]
      )
    end

    # 概要・目的: 「normalizes current assistant messages from dotted event types into canonical helper
    #   fields」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「normalizes current assistant messages from dotted event types into canonical helper
    #   fields」の条件・入力・操作を実行する。
    # 期待値: current assistant messages from dotted event types into canonical helper fields が正規化されること。
    it "normalizes current assistant messages from dotted event types into canonical helper fields" do
      result = normalizer.call(
        raw_event: {
          "type" => "assistant.message",
          "data" => {
            "content" => "I can inspect the latest sessions.",
            "toolRequests" => [
              {
                "name" => "functions.bash",
                "arguments" => {
                  "command" => "git --no-pager status",
                  "description" => "Inspect repository status"
                }
              }
            ]
          },
          "timestamp" => "2026-04-28T01:00:04Z"
        },
        source_format: :current,
        sequence: 5
      )

      expect(result).to eq(
        CopilotHistory::Types::NormalizationResult.new(
          event: CopilotHistory::Types::NormalizedEvent.new(
            sequence: 5,
            kind: :message,
            mapping_status: :complete,
            raw_type: "assistant.message",
            occurred_at: "2026-04-28T01:00:04Z",
            role: "assistant",
            content: "I can inspect the latest sessions.",
            tool_calls: [
              CopilotHistory::Types::NormalizedToolCall.new(
                name: "functions.bash",
                arguments_preview: "{\"command\":\"git --no-pager status\",\"description\":\"Inspect repository status\"}",
                is_truncated: false,
                status: :complete
              )
            ],
            detail: nil,
            raw_payload: {
              "type" => "assistant.message",
              "data" => {
                "content" => "I can inspect the latest sessions.",
                "toolRequests" => [
                  {
                    "name" => "functions.bash",
                    "arguments" => {
                      "command" => "git --no-pager status",
                      "description" => "Inspect repository status"
                    }
                  }
                ]
              },
              "timestamp" => "2026-04-28T01:00:04Z"
            }
          ),
          issues: []
        )
      )
    end

    # 概要・目的: 「normalizes current non-message events into detail or unknown events without dropping raw
    #   payload」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「normalizes current non-message events into detail or unknown events without dropping raw
    #   payload」の条件・入力・操作を実行する。
    # 期待値: current non-message events into detail or unknown events without dropping raw payload が正規化されること。
    it "normalizes current non-message events into detail or unknown events without dropping raw payload" do
      detail_result = normalizer.call(
        raw_event: {
          "type" => "hook.start",
          "data" => {
            "hookEventName" => "before-tool",
            "matcher" => "*"
          },
          "timestamp" => "2026-04-28T02:00:03Z"
        },
        source_format: :current,
        sequence: 3
      )
      unknown_result = normalizer.call(
        raw_event: {
          "type" => "mystery.event",
          "data" => {
            "value" => 42
          },
          "timestamp" => "2026-04-28T02:00:04Z"
        },
        source_format: :current,
        sequence: 4
      )

      expect(detail_result.event).to eq(
        CopilotHistory::Types::NormalizedEvent.new(
          sequence: 3,
          kind: :detail,
          mapping_status: :complete,
          raw_type: "hook.start",
          occurred_at: "2026-04-28T02:00:03Z",
          role: nil,
          content: nil,
          tool_calls: [],
          detail: {
            category: "hook",
            title: "hook.start",
            body: "before-tool / *"
          },
          raw_payload: {
            "type" => "hook.start",
            "data" => {
              "hookEventName" => "before-tool",
              "matcher" => "*"
            },
            "timestamp" => "2026-04-28T02:00:03Z"
          }
        )
      )
      expect(detail_result.issues).to eq([])

      expect(unknown_result.event.kind).to eq(:unknown)
      expect(unknown_result.event.mapping_status).to eq(:complete)
      expect(unknown_result.event.raw_payload).to eq(
        "type" => "mystery.event",
        "data" => { "value" => 42 },
        "timestamp" => "2026-04-28T02:00:04Z"
      )
      expect(unknown_result.issues).to eq(
        [
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
            message: "event payload could not be mapped to canonical fields",
            source_path: source_path,
            sequence: 4,
            severity: :warning
          )
        ]
      )
    end

    # 概要・目的: 「applies redaction and truncation to current tool request summaries without dropping the message
    #   body」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「applies redaction and truncation to current tool request summaries without dropping the message
    #   body」の条件・入力・操作を実行する。
    # 期待値: redaction and truncation to current tool request summaries without dropping the message body
    #   が適用されること。
    it "applies redaction and truncation to current tool request summaries without dropping the message body" do
      result = normalizer.call(
        raw_event: {
          "type" => "assistant.message",
          "data" => {
            "content" => "I can summarize the request.",
            "toolRequests" => [
              {
                "name" => "functions.bash",
                "arguments" => {
                  "command" => "printenv",
                  "token" => "super-secret-token",
                  "description" => "x" * 400
                }
              }
            ]
          },
          "timestamp" => "2026-04-28T03:00:04Z"
        },
        source_format: :current,
        sequence: 6
      )

      expect(result.event).to have_attributes(
        kind: :message,
        mapping_status: :complete,
        role: "assistant",
        content: "I can summarize the request."
      )
      expect(result.event.tool_calls).to eq(
        [
          CopilotHistory::Types::NormalizedToolCall.new(
            name: "functions.bash",
            arguments_preview: result.event.tool_calls.first.arguments_preview,
            is_truncated: true,
            status: :complete
          )
        ]
      )
      expect(result.event.tool_calls.first.arguments_preview).to include("\"token\":\"[REDACTED]\"")
      expect(result.event.tool_calls.first.arguments_preview.length).to eq(240)
      expect(result.issues).to eq([])
    end

    # 概要・目的: 「classifies skill.invoked current events as detail events with a canonical summary」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「classifies skill.invoked current events as detail events with a canonical
    #   summary」の条件・入力・操作を実行する。
    # 期待値: skill.invoked current events が detail events with a canonical summary として分類されること。
    it "classifies skill.invoked current events as detail events with a canonical summary" do
      result = normalizer.call(
        raw_event: {
          "type" => "skill.invoked",
          "data" => {
            "skillName" => "kiro-review",
            "toolName" => "functions.skill"
          },
          "timestamp" => "2026-04-28T04:00:04Z"
        },
        source_format: :current,
        sequence: 7
      )

      expect(result.event).to eq(
        CopilotHistory::Types::NormalizedEvent.new(
          sequence: 7,
          kind: :detail,
          mapping_status: :complete,
          raw_type: "skill.invoked",
          occurred_at: "2026-04-28T04:00:04Z",
          role: nil,
          content: nil,
          tool_calls: [],
          detail: {
            category: "skill",
            title: "skill.invoked",
            body: "kiro-review / functions.skill"
          },
          raw_payload: {
            "type" => "skill.invoked",
            "data" => {
              "skillName" => "kiro-review",
              "toolName" => "functions.skill"
            },
            "timestamp" => "2026-04-28T04:00:04Z"
          }
        )
      )
      expect(result.issues).to eq([])
    end

    include_examples "a known normalized message", :current
    include_examples "a known normalized message", :legacy
    include_examples "a partially normalized message", :current
    include_examples "a partially normalized message", :legacy
    include_examples "an unknown normalized event", :current
    include_examples "an unknown normalized event", :legacy
  end
end

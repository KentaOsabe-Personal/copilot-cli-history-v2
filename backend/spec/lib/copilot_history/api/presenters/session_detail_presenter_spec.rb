require "rails_helper"

RSpec.describe CopilotHistory::Api::Presenters::SessionDetailPresenter do
  subject(:presenter) { described_class.new }

  describe "#call" do
    # 概要・目的: 「keeps session issues in the header and groups event issues onto their matching timeline
    #   events」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps session issues in the header and groups event issues onto their matching timeline
    #   events」の条件・入力・操作を実行する。
    # 期待値: session issues in the header が維持され、groups event issues onto their matching timeline eventsこと。
    it "keeps session issues in the header and groups event issues onto their matching timeline events" do
      session_issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::LEGACY_JSON_PARSE_FAILED,
        message: "legacy session JSON could not be parsed",
        source_path: "/tmp/copilot/history-session-state/legacy-mixed.json",
        severity: :error
      )
      event_issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "event payload matched partially",
        source_path: "/tmp/copilot/history-session-state/legacy-mixed.json",
        sequence: 2,
        severity: :warning
      )
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "legacy-mixed",
          source_format: :legacy,
          created_at: "2026-04-26T07:50:00Z",
          updated_at: nil,
          selected_model: "gpt-5.4",
          events: [
            build_event(
              sequence: 1,
              raw_type: "assistant_message",
              occurred_at: "2026-04-26T07:50:01Z",
              role: "assistant",
              content: "legacy mixed event",
              raw_payload: {
                "type" => "assistant_message",
                "role" => "assistant",
                "content" => "legacy mixed event",
                "timestamp" => "2026-04-26T07:50:01Z"
              }
            ),
            build_event(
              sequence: 2,
              mapping_status: :partial,
              raw_type: "assistant_message",
              occurred_at: nil,
              role: "assistant",
              content: "legacy partial event",
              raw_payload: {
                "type" => "assistant_message",
                "role" => "assistant",
                "content" => "legacy partial event"
              }
            )
          ],
          message_snapshots: [
            CopilotHistory::Types::MessageSnapshot.new(
              role: "assistant",
              content: "legacy mixed transcript",
              raw_payload: { "role" => "assistant", "content" => "legacy mixed transcript" }
            )
          ],
          issues: [ session_issue, event_issue ],
          source_paths: {
            source: "/tmp/copilot/history-session-state/legacy-mixed.json"
          }
        )
      )

      payload = presenter.call(result: result).fetch(:data)

      expect(payload).to include(
          id: "legacy-mixed",
          source_format: "legacy",
          created_at: "2026-04-26T07:50:00Z",
          updated_at: nil,
          work_context: {
            cwd: nil,
            git_root: nil,
            repository: nil,
            branch: nil
          },
          selected_model: "gpt-5.4",
          source_state: "complete",
          degraded: true,
          raw_included: false,
          issues: [
            {
              code: "legacy.json_parse_failed",
              severity: "error",
              message: "legacy session JSON could not be parsed",
              source_path: "/tmp/copilot/history-session-state/legacy-mixed.json",
              scope: "session",
              event_sequence: nil
            }
          ],
          message_snapshots: [
            {
              role: "assistant",
              content: "legacy mixed transcript",
              raw_payload: nil
            }
          ],
          conversation: {
            entries: [
              {
                sequence: 1,
                role: "assistant",
                content: "legacy mixed event",
                occurred_at: "2026-04-26T07:50:01Z",
                tool_calls: [],
                degraded: false,
                issues: []
              },
              {
                sequence: 2,
                role: "assistant",
                content: "legacy partial event",
                occurred_at: nil,
                tool_calls: [],
                degraded: true,
                issues: [
                  {
                    code: "event.partial_mapping",
                    severity: "warning",
                    message: "event payload matched partially",
                    source_path: "/tmp/copilot/history-session-state/legacy-mixed.json",
                    scope: "event",
                    event_sequence: 2
                  }
                ]
              }
            ],
            message_count: 2,
            empty_reason: nil,
            summary: {
              has_conversation: true,
              message_count: 2,
              preview: "legacy mixed event",
              activity_count: 0
            }
          },
          activity: {
            entries: []
          },
          timeline: [
            {
              sequence: 1,
              kind: "message",
              mapping_status: "complete",
              raw_type: "assistant_message",
              occurred_at: "2026-04-26T07:50:01Z",
              role: "assistant",
              content: "legacy mixed event",
              tool_calls: [],
              detail: nil,
              raw_payload: nil,
              degraded: false,
              issues: []
            },
            {
              sequence: 2,
              kind: "message",
              mapping_status: "partial",
              raw_type: "assistant_message",
              occurred_at: nil,
              role: "assistant",
              content: "legacy partial event",
              tool_calls: [],
              detail: nil,
              raw_payload: nil,
              degraded: true,
              issues: [
                {
                  code: "event.partial_mapping",
                  severity: "warning",
                  message: "event payload matched partially",
                  source_path: "/tmp/copilot/history-session-state/legacy-mixed.json",
                  scope: "event",
                  event_sequence: 2
                }
              ]
            }
          ]
      )
    end

    # 概要・目的: 「returns an empty message_snapshots array for current sessions」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns an empty message_snapshots array for current sessions」の条件・入力・操作を実行する。
    # 期待値: an empty message_snapshots array for current sessions を返すこと。
    it "returns an empty message_snapshots array for current sessions" do
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "current-mixed",
          source_format: :current,
          cwd: "/workspace/current-mixed",
          git_root: "/workspace/current-mixed",
          repository: "octo/example",
          branch: "feature/history",
          created_at: "2026-04-26T10:00:00Z",
          updated_at: "2026-04-26T10:05:00Z",
          selected_model: nil,
          events: [],
          message_snapshots: [],
          issues: [],
          source_paths: {
            workspace: "/tmp/copilot/session-state/current-mixed/workspace.yaml",
            events: "/tmp/copilot/session-state/current-mixed/events.jsonl"
          }
        )
      )

      expect(presenter.call(result: result).dig(:data, :message_snapshots)).to eq([])
    end

    # 概要・目的: 「maps current detail into conversation, activity, timeline, and omits raw payloads by
    #   default」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「maps current detail into conversation, activity, timeline, and omits raw payloads by
    #   default」の条件・入力・操作を実行する。
    # 期待値: 「maps current detail into conversation, activity, timeline, and omits raw payloads by
    #   default」で示す状態または振る舞いが成立すること。
    it "maps current detail into conversation, activity, timeline, and omits raw payloads by default" do
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "current-schema-valid",
          source_format: :current,
          created_at: "2026-04-28T01:00:00Z",
          updated_at: "2026-04-28T01:02:00Z",
          selected_model: nil,
          events: [
            build_event(
              sequence: 1,
              raw_type: "assistant.message",
              occurred_at: "2026-04-28T01:00:04Z",
              role: "assistant",
              content: "I can inspect the latest sessions.",
              tool_calls: [
                CopilotHistory::Types::NormalizedToolCall.new(
                  name: "functions.bash",
                  arguments_preview: "{\"command\":\"git --no-pager status\"}",
                  is_truncated: false,
                  status: :complete
                )
              ]
            ),
            build_event(
              sequence: 2,
              kind: :detail,
              raw_type: "tool.execution_start",
              occurred_at: "2026-04-28T01:00:05Z",
              detail: {
                category: "tool_execution",
                title: "tool.execution_start",
                body: "functions.bash / tool-1"
              },
              raw_payload: {
                "type" => "tool.execution_start"
              }
            )
          ],
          message_snapshots: [],
          issues: [],
          source_paths: {
            workspace: "/tmp/copilot/session-state/current-schema-valid/workspace.yaml",
            events: "/tmp/copilot/session-state/current-schema-valid/events.jsonl"
          }
        )
      )

      payload = presenter.call(result: result).fetch(:data)

      expect(payload.fetch(:raw_included)).to eq(false)
      expect(payload.fetch(:conversation)).to eq(
        {
          entries: [
            {
              sequence: 1,
              role: "assistant",
              content: "I can inspect the latest sessions.",
              occurred_at: "2026-04-28T01:00:04Z",
              tool_calls: [
                {
                  name: "functions.bash",
                  arguments_preview: "{\"command\":\"git --no-pager status\"}",
                  is_truncated: false,
                  status: "complete"
                }
              ],
              degraded: false,
              issues: []
            }
          ],
          message_count: 1,
          empty_reason: nil,
          summary: {
            has_conversation: true,
            message_count: 1,
            preview: "I can inspect the latest sessions.",
            activity_count: 1
          }
        }
      )
      expect(payload.fetch(:activity)).to eq(
        {
          entries: [
            {
              sequence: 2,
              category: "tool_execution",
              title: "tool.execution_start",
              summary: "functions.bash / tool-1",
              raw_type: "tool.execution_start",
              mapping_status: "complete",
              occurred_at: "2026-04-28T01:00:05Z",
              source_path: "/tmp/copilot/session-state/current-schema-valid/events.jsonl",
              raw_available: true,
              raw_payload: nil,
              degraded: false,
              issues: []
            }
          ]
        }
      )
      expect(payload.fetch(:timeline)).to eq(
        [
          {
            sequence: 1,
            kind: "message",
            mapping_status: "complete",
            raw_type: "assistant.message",
            occurred_at: "2026-04-28T01:00:04Z",
            role: "assistant",
            content: "I can inspect the latest sessions.",
            tool_calls: [
              {
                name: "functions.bash",
                arguments_preview: "{\"command\":\"git --no-pager status\"}",
                is_truncated: false,
                status: "complete"
              }
            ],
            detail: nil,
            raw_payload: nil,
            degraded: false,
            issues: []
          },
          {
            sequence: 2,
            kind: "detail",
            mapping_status: "complete",
            raw_type: "tool.execution_start",
            occurred_at: "2026-04-28T01:00:05Z",
            role: nil,
            content: nil,
            tool_calls: [],
            detail: {
              category: "tool_execution",
              title: "tool.execution_start",
              body: "functions.bash / tool-1"
            },
            raw_payload: nil,
            degraded: false,
            issues: []
          }
        ]
      )
    end

    # 概要・目的: 「keeps tool-only conversation entries and their utterance issues in the existing detail
    #   schema」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps tool-only conversation entries and their utterance issues in the existing detail
    #   schema」の条件・入力・操作を実行する。
    # 期待値: tool-only conversation entries が維持され、their utterance issues in the existing detail schemaこと。
    it "keeps tool-only conversation entries and their utterance issues in the existing detail schema" do
      utterance_issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "event payload matched partially",
        source_path: "/tmp/copilot/session-state/current-model-with-values/events.jsonl",
        sequence: 1,
        severity: :warning
      )
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "current-model-with-values",
          source_format: :current,
          created_at: "2026-04-29T00:00:00Z",
          updated_at: "2026-04-29T00:00:02Z",
          selected_model: "gpt-5-current",
          events: [
            build_event(
              sequence: 1,
              raw_type: "assistant.message",
              occurred_at: "2026-04-29T00:00:01Z",
              role: "assistant",
              content: nil,
              tool_calls: [
                CopilotHistory::Types::NormalizedToolCall.new(
                  name: "skill-context",
                  arguments_preview: "{\"context\":\"trimmed\"}",
                  is_truncated: false,
                  status: :complete
                )
              ]
            )
          ],
          message_snapshots: [],
          issues: [ utterance_issue ],
          source_paths: {
            workspace: "/tmp/copilot/session-state/current-model-with-values/workspace.yaml",
            events: "/tmp/copilot/session-state/current-model-with-values/events.jsonl"
          }
        )
      )

      payload = presenter.call(result: result).fetch(:data)

      expect(payload.fetch(:selected_model)).to eq("gpt-5-current")
      expect(payload.fetch(:conversation)).to eq(
        entries: [
          {
            sequence: 1,
            role: "assistant",
            content: "",
            occurred_at: "2026-04-29T00:00:01Z",
            tool_calls: [
              {
                name: "skill-context",
                arguments_preview: "{\"context\":\"trimmed\"}",
                is_truncated: false,
                status: "complete"
              }
            ],
            degraded: true,
            issues: [
              {
                code: "event.partial_mapping",
                severity: "warning",
                message: "event payload matched partially",
                source_path: "/tmp/copilot/session-state/current-model-with-values/events.jsonl",
                scope: "event",
                event_sequence: 1
              }
            ]
          }
        ],
        message_count: 1,
        empty_reason: nil,
        summary: {
          has_conversation: true,
          message_count: 1,
          preview: nil,
          activity_count: 0
        }
      )
    end

    # 概要・目的: 「includes raw payloads only when explicitly requested」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「includes raw payloads only when explicitly requested」の条件・入力・操作を実行する。
    # 期待値: 「includes raw payloads only when explicitly requested」で示す状態または振る舞いが成立すること。
    it "includes raw payloads only when explicitly requested" do
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "current-schema-valid",
          source_format: :current,
          created_at: "2026-04-28T01:00:00Z",
          updated_at: "2026-04-28T01:02:00Z",
          selected_model: nil,
          events: [
            build_event(
              sequence: 1,
              raw_type: "tool.execution_start",
              occurred_at: "2026-04-28T01:00:05Z",
              kind: :detail,
              detail: {
                category: "tool_execution",
                title: "tool.execution_start",
                body: "functions.bash / tool-1"
              },
              raw_payload: {
                "type" => "tool.execution_start"
              }
            )
          ],
          message_snapshots: [],
          issues: [],
          source_paths: {
            workspace: "/tmp/copilot/session-state/current-schema-valid/workspace.yaml",
            events: "/tmp/copilot/session-state/current-schema-valid/events.jsonl"
          }
        )
      )

      payload = presenter.call(result: result, include_raw: true).fetch(:data)

      expect(payload.fetch(:raw_included)).to eq(true)
      expect(payload.fetch(:timeline).first.fetch(:raw_payload)).to eq({ "type" => "tool.execution_start" })
      expect(payload.dig(:activity, :entries).first.fetch(:raw_payload)).to eq({ "type" => "tool.execution_start" })
    end

    # 概要・目的: 「keeps unmatched event issues in the session issue list so invalid lines remain visible」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「keeps unmatched event issues in the session issue list so invalid lines remain
    #   visible」の条件・入力・操作を実行する。
    # 期待値: unmatched event issues in the session issue list so invalid lines remain visible が維持されること。
    it "keeps unmatched event issues in the session issue list so invalid lines remain visible" do
      unmatched_event_issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
        message: "events.jsonl line could not be parsed",
        source_path: "/tmp/copilot/session-state/current-schema-degraded/events.jsonl",
        sequence: 5,
        severity: :error
      )
      result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(
        root: build_root,
        session: CopilotHistory::Types::NormalizedSession.new(
          session_id: "current-schema-degraded",
          source_format: :current,
          created_at: "2026-04-28T02:00:00Z",
          updated_at: "2026-04-28T02:03:00Z",
          selected_model: nil,
          events: [
            build_event(
              sequence: 1,
              raw_type: "user.message",
              occurred_at: "2026-04-28T02:00:01Z",
              role: "user",
              content: "run diagnostics",
              raw_payload: {
                "type" => "user.message"
              }
            )
          ],
          message_snapshots: [],
          issues: [ unmatched_event_issue ],
          source_paths: {
            workspace: "/tmp/copilot/session-state/current-schema-degraded/workspace.yaml",
            events: "/tmp/copilot/session-state/current-schema-degraded/events.jsonl"
          }
        )
      )

      payload = presenter.call(result: result).fetch(:data)

      expect(payload).to include(
          id: "current-schema-degraded",
          source_format: "current",
          created_at: "2026-04-28T02:00:00Z",
          updated_at: "2026-04-28T02:03:00Z",
          work_context: {
            cwd: nil,
            git_root: nil,
            repository: nil,
            branch: nil
          },
          selected_model: nil,
          source_state: "complete",
          degraded: true,
          raw_included: false,
          issues: [
            {
              code: "current.event_parse_failed",
              severity: "error",
              message: "events.jsonl line could not be parsed",
              source_path: "/tmp/copilot/session-state/current-schema-degraded/events.jsonl",
              scope: "event",
              event_sequence: 5
            }
          ],
          message_snapshots: [],
          conversation: {
            entries: [
              {
                sequence: 1,
                role: "user",
                content: "run diagnostics",
                occurred_at: "2026-04-28T02:00:01Z",
                tool_calls: [],
                degraded: false,
                issues: []
              }
            ],
            message_count: 1,
            empty_reason: nil,
            summary: {
              has_conversation: true,
              message_count: 1,
              preview: "run diagnostics",
              activity_count: 0
            }
          },
          activity: {
            entries: []
          },
          timeline: [
            {
              sequence: 1,
              kind: "message",
              mapping_status: "complete",
              raw_type: "user.message",
              occurred_at: "2026-04-28T02:00:01Z",
              role: "user",
              content: "run diagnostics",
              tool_calls: [],
              detail: nil,
              raw_payload: nil,
              degraded: false,
              issues: []
            }
          ]
      )
    end
  end

  def build_root
    CopilotHistory::Types::ResolvedHistoryRoot.new(
      root_path: "/tmp/copilot",
      current_root: "/tmp/copilot/session-state",
      legacy_root: "/tmp/copilot/history-session-state"
    )
  end

  def build_event(sequence:, raw_type:, occurred_at:, role: nil, content: nil, kind: :message, mapping_status: :complete, tool_calls: [], detail: nil, raw_payload: nil)
    CopilotHistory::Types::NormalizedEvent.new(
      sequence: sequence,
      kind: kind,
      mapping_status: mapping_status,
      raw_type: raw_type,
      occurred_at: occurred_at,
      role: role,
      content: content,
      tool_calls: tool_calls,
      detail: detail,
      raw_payload: raw_payload
    )
  end
end

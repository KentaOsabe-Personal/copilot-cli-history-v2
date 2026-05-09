require "rails_helper"

RSpec.describe CopilotHistory::Projections::ConversationProjector, :copilot_history do
  subject(:projector) { described_class.new }

  describe "#call" do
    # 概要・目的: 「projects user and assistant messages with content or tool calls in source sequence
    #   order」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「projects user and assistant messages with content or tool calls in source sequence
    #   order」の条件・入力・操作を実行する。
    # 期待値: 「projects user and assistant messages with content or tool calls in source sequence
    #   order」で示す状態または振る舞いが成立すること。
    it "projects user and assistant messages with content or tool calls in source sequence order" do
      with_copilot_history_fixture("current_schema_valid") do |root|
        session = read_first_current_session(root)

        projection = projector.call(session)

        expect(projection.entries.map { |entry| [ entry.sequence, entry.role, entry.content ] }).to eq(
          [
            [ 2, "user", "show recent sessions" ],
            [ 4, "assistant", "I can inspect the latest sessions." ],
            [ 5, "assistant", "" ]
          ]
        )
        expect(projection.entries.last.tool_calls.map(&:name)).to eq([ "functions.bash" ])
        expect(projection.message_count).to eq(3)
        expect(projection.empty_reason).to be_nil
      end
    end

    # 概要・目的: 「keeps legacy user and assistant messages in the same projection contract」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps legacy user and assistant messages in the same projection contract」の条件・入力・操作を実行する。
    # 期待値: legacy user が維持され、assistant messages in the same projection contractこと。
    it "keeps legacy user and assistant messages in the same projection contract" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        session = read_session(root, "legacy-schema-mixed")

        projection = projector.call(session)

        expect(projection.entries.map { |entry| [ entry.sequence, entry.role, entry.content ] }).to eq(
          [
            [ 1, "user", "legacy mixed question" ],
            [ 2, "assistant", "legacy mixed answer" ]
          ]
        )
        expect(projection.summary).to have_attributes(
          has_conversation: true,
          message_count: 2,
          preview: "legacy mixed question"
        )
      end
    end

    # 概要・目的: 「returns a stable empty reason when events exist but no conversation messages qualify」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns a stable empty reason when events exist but no conversation messages
    #   qualify」の条件・入力・操作を実行する。
    # 期待値: a stable empty reason when events exist but no conversation messages qualify を返すこと。
    it "returns a stable empty reason when events exist but no conversation messages qualify" do
      session = CopilotHistory::Types::NormalizedSession.new(
        session_id: "activity-only",
        source_format: :current,
        events: [
          build_event(sequence: 1, kind: :message, raw_type: "system.message", role: "system", content: "internal"),
          build_event(sequence: 2, kind: :detail, raw_type: "tool.execution_start", detail: { category: "tool_execution" })
        ],
        message_snapshots: [],
        issues: [],
        source_paths: {}
      )

      projection = projector.call(session)

      expect(projection.entries).to eq([])
      expect(projection.message_count).to eq(0)
      expect(projection.empty_reason).to eq("no_conversation_messages")
      expect(projection.summary).to have_attributes(
        has_conversation: false,
        message_count: 0,
        preview: nil
      )
    end

    # 概要・目的: 「uses no_events as the empty reason when a session has no normalized events」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「uses no_events as the empty reason when a session has no normalized events」の条件・入力・操作を実行する。
    # 期待値: no_events as the empty reason when a session has no normalized events が使われること。
    it "uses no_events as the empty reason when a session has no normalized events" do
      session = CopilotHistory::Types::NormalizedSession.new(
        session_id: "workspace-only",
        source_format: :current,
        source_state: :workspace_only,
        events: [],
        message_snapshots: [],
        issues: [],
        source_paths: {}
      )

      expect(projector.call(session).empty_reason).to eq("no_events")
    end

    # 概要・目的: 「uses events_unavailable when current events could not be normalized」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「uses events_unavailable when current events could not be normalized」の条件・入力・操作を実行する。
    # 期待値: events_unavailable when current events could not be normalized が使われること。
    it "uses events_unavailable when current events could not be normalized" do
      session = CopilotHistory::Types::NormalizedSession.new(
        session_id: "unreadable-events",
        source_format: :current,
        source_state: :degraded,
        events: [],
        message_snapshots: [],
        issues: [
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_UNREADABLE,
            message: "events.jsonl is not accessible",
            source_path: Pathname.new("/tmp/events.jsonl"),
            severity: :error
          )
        ],
        source_paths: {}
      )

      expect(projector.call(session).empty_reason).to eq("events_unavailable")
    end

    # 概要・目的: 「projects tool-only user and assistant messages from the shared current model fixture」を通じて、reader
    #   と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「projects tool-only user and assistant messages from the shared current model
    #   fixture」の条件・入力・操作を実行する。
    # 期待値: 「projects tool-only user and assistant messages from the shared current model
    #   fixture」で示す状態または振る舞いが成立すること。
    it "projects tool-only user and assistant messages from the shared current model fixture" do
      with_copilot_history_fixture("current_model") do |root|
        session = read_session(root, "current-model-with-values")

        projection = projector.call(session)
        tool_only_entries = projection.entries.select { |entry| entry.content.to_s.empty? && entry.tool_calls.any? }

        expect(tool_only_entries.map { |entry| [ entry.role, entry.tool_calls.first.name ] }).to eq(
          [
            [ "assistant", "skill-context" ],
            [ "user", "functions.submit_feedback" ]
          ]
        )
        expect(tool_only_entries.map(&:degraded)).to eq([ false, false ])
        expect(tool_only_entries.map(&:issues)).to eq([ [], [] ])
        expect(tool_only_entries.first.tool_calls.first.arguments_preview).to include("long skill context")
      end
    end

    # 概要・目的: 「keeps tool-only messages with their utterance issues and excludes empty messages without tool
    #   calls」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps tool-only messages with their utterance issues and excludes empty messages without tool
    #   calls」の条件・入力・操作を実行する。
    # 期待値: tool-only messages with their utterance issues が維持され、excludes empty messages without tool callsこと。
    it "keeps tool-only messages with their utterance issues and excludes empty messages without tool calls" do
      utterance_issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "event payload matched partially",
        source_path: Pathname.new("/tmp/events.jsonl"),
        sequence: 2,
        severity: :warning
      )
      session = CopilotHistory::Types::NormalizedSession.new(
        session_id: "tool-only-with-issue",
        source_format: :current,
        events: [
          build_event(sequence: 1, kind: :message, raw_type: "user.message", role: "user", content: nil),
          build_event(
            sequence: 2,
            kind: :message,
            raw_type: "assistant.message",
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
        source_paths: {}
      )

      projection = projector.call(session)

      expect(projection.entries.map(&:sequence)).to eq([ 2 ])
      expect(projection.entries.first).to have_attributes(
        role: "assistant",
        content: "",
        degraded: true,
        issues: [ utterance_issue ]
      )
      expect(projection.entries.first.tool_calls.map(&:name)).to eq([ "skill-context" ])
      expect(projection.empty_reason).to be_nil
    end
  end

  def read_first_current_session(root)
    source = CopilotHistory::SessionSourceCatalog.new.call(resolved_root(root)).find { |candidate| candidate.format == :current }
    CopilotHistory::CurrentSessionReader.new.call(source)
  end

  def read_session(root, session_id)
    source = CopilotHistory::SessionSourceCatalog.new.call(resolved_root(root)).find { |candidate| candidate.session_id == session_id }

    case source.format
    when :current
      CopilotHistory::CurrentSessionReader.new.call(source)
    when :legacy
      CopilotHistory::LegacySessionReader.new.call(source)
    end
  end

  def resolved_root(root)
    CopilotHistory::Types::ResolvedHistoryRoot.new(
      root_path: root,
      current_root: root.join("session-state"),
      legacy_root: root.join("history-session-state")
    )
  end

  def build_event(sequence:, kind:, raw_type:, role: nil, content: nil, tool_calls: [], detail: nil)
    CopilotHistory::Types::NormalizedEvent.new(
      sequence: sequence,
      kind: kind,
      raw_type: raw_type,
      occurred_at: nil,
      role: role,
      content: content,
      tool_calls: tool_calls,
      detail: detail,
      raw_payload: { "type" => raw_type }
    )
  end
end

require "rails_helper"

RSpec.describe "CopilotHistory normalized contracts" do
  describe CopilotHistory::Types::NormalizedEvent do
    # 概要・目的: 「retains canonical event fields, helper defaults, and raw payload」を通じて、正規化・projection・presenter
    #   の変換契約を検証する。
    # テストケース: 「retains canonical event fields, helper defaults, and raw payload」の条件・入力・操作を実行する。
    # 期待値: 「retains canonical event fields, helper defaults, and raw payload」で示す状態または振る舞いが成立すること。
    it "retains canonical event fields, helper defaults, and raw payload" do
      event = described_class.new(
        sequence: 7,
        kind: :unknown,
        mapping_status: :complete,
        raw_type: "mystery-event",
        occurred_at: "2026-04-26T10:00:00Z",
        role: nil,
        content: nil,
        tool_calls: [],
        detail: nil,
        raw_payload: { "type" => "mystery-event", "payload" => { "value" => 1 } }
      )

      expect(event.sequence).to eq(7)
      expect(event.kind).to eq(:unknown)
      expect(event.mapping_status).to eq(:complete)
      expect(event.raw_type).to eq("mystery-event")
      expect(event.occurred_at).to eq(Time.iso8601("2026-04-26T10:00:00Z"))
      expect(event.tool_calls).to eq([])
      expect(event.detail).to be_nil
      expect(event.raw_payload).to eq(
        "type" => "mystery-event",
        "payload" => { "value" => 1 }
      )
    end
  end

  describe CopilotHistory::Types::NormalizedToolCall do
    # 概要・目的: 「normalizes one tool request summary into the fixed backend helper
    #   shape」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「normalizes one tool request summary into the fixed backend helper shape」の条件・入力・操作を実行する。
    # 期待値: one tool request summary into the fixed backend helper shape が正規化されること。
    it "normalizes one tool request summary into the fixed backend helper shape" do
      tool_call = described_class.new(
        name: "functions.bash",
        arguments_preview: "{\"command\":\"git status\"}",
        is_truncated: false,
        status: :complete
      )

      expect(tool_call.name).to eq("functions.bash")
      expect(tool_call.arguments_preview).to eq("{\"command\":\"git status\"}")
      expect(tool_call.is_truncated).to be(false)
      expect(tool_call.status).to eq(:complete)
    end
  end

  describe CopilotHistory::Types::MessageSnapshot do
    # 概要・目的: 「preserves supplemental transcript entries apart from canonical events」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「preserves supplemental transcript entries apart from canonical events」の条件・入力・操作を実行する。
    # 期待値: supplemental transcript entries apart from canonical events が保持されること。
    it "preserves supplemental transcript entries apart from canonical events" do
      snapshot = described_class.new(
        role: "user",
        content: "show me recent sessions",
        raw_payload: { "role" => "user", "content" => "show me recent sessions" }
      )

      expect(snapshot.role).to eq("user")
      expect(snapshot.content).to eq("show me recent sessions")
      expect(snapshot.raw_payload).to eq(
        "role" => "user",
        "content" => "show me recent sessions"
      )
    end
  end

  describe CopilotHistory::Types::NormalizationResult do
    # 概要・目的: 「wraps one normalized event with any read issues emitted during mapping」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「wraps one normalized event with any read issues emitted during mapping」の条件・入力・操作を実行する。
    # 期待値: one normalized event with any read issues emitted during mapping が公開用 envelope に包まれること。
    it "wraps one normalized event with any read issues emitted during mapping" do
      event = CopilotHistory::Types::NormalizedEvent.new(
        sequence: 2,
        kind: :message,
        mapping_status: :partial,
        raw_type: "assistant_turn",
        occurred_at: nil,
        role: "assistant",
        content: nil,
        tool_calls: [],
        detail: nil,
        raw_payload: { "type" => "assistant_turn" }
      )
      issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "content is unavailable",
        source_path: "/tmp/events.jsonl",
        sequence: 2,
        severity: :warning
      )

      result = described_class.new(event:, issues: [ issue ])

      expect(result.event).to eq(event)
      expect(result.issues).to eq([ issue ])
    end
  end

  describe CopilotHistory::Types::NormalizedSession do
    # 概要・目的: 「keeps canonical events separate from supplemental message snapshots」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps canonical events separate from supplemental message snapshots」の条件・入力・操作を実行する。
    # 期待値: canonical events separate from supplemental message snapshots が維持されること。
    it "keeps canonical events separate from supplemental message snapshots" do
      event = CopilotHistory::Types::NormalizedEvent.new(
        sequence: 1,
        kind: :message,
        mapping_status: :complete,
        raw_type: "user_message",
        occurred_at: "2026-04-26T10:00:00Z",
        role: "user",
        content: "open the latest session",
        tool_calls: [],
        detail: nil,
        raw_payload: { "type" => "user_message" }
      )
      snapshot = CopilotHistory::Types::MessageSnapshot.new(
        role: "assistant",
        content: "Sure",
        raw_payload: { "role" => "assistant", "content" => "Sure" }
      )
      issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
        message: "one event was preserved as raw payload",
        source_path: "/tmp/history.json",
        sequence: 9,
        severity: :warning
      )

      session = described_class.new(
        session_id: "session-123",
        source_format: :legacy,
        source_state: :degraded,
        cwd: "/repo",
        git_root: "/repo",
        repository: "example/repo",
        branch: "main",
        created_at: "2026-04-26T09:55:00Z",
        updated_at: "2026-04-26T10:05:00Z",
        selected_model: "gpt-5.4",
        events: [ event ],
        message_snapshots: [ snapshot ],
        issues: [ issue ],
        source_paths: {
          source: "/tmp/history-session-state/session-123.json"
        }
      )

      expect(session.session_id).to eq("session-123")
      expect(session.source_format).to eq(:legacy)
      expect(session.source_state).to eq(:degraded)
      expect(session.cwd).to eq(Pathname("/repo"))
      expect(session.git_root).to eq(Pathname("/repo"))
      expect(session.repository).to eq("example/repo")
      expect(session.branch).to eq("main")
      expect(session.created_at).to eq(Time.iso8601("2026-04-26T09:55:00Z"))
      expect(session.updated_at).to eq(Time.iso8601("2026-04-26T10:05:00Z"))
      expect(session.selected_model).to eq("gpt-5.4")
      expect(session.events).to eq([ event ])
      expect(session.message_snapshots).to eq([ snapshot ])
      expect(session.issues).to eq([ issue ])
      expect(session.source_paths).to eq(
        source: Pathname("/tmp/history-session-state/session-123.json")
      )
    end

    # 概要・目的: 「defaults source state to complete and rejects unsupported states」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「defaults source state to complete and rejects unsupported states」の条件・入力・操作を実行する。
    # 期待値: 「defaults source state to complete and rejects unsupported states」で示す状態または振る舞いが成立すること。
    it "defaults source state to complete and rejects unsupported states" do
      event = CopilotHistory::Types::NormalizedEvent.new(
        sequence: 1,
        kind: :message,
        raw_type: "user_message",
        occurred_at: "2026-04-26T10:00:00Z",
        role: "user",
        content: "hello",
        raw_payload: { "type" => "user_message" }
      )

      session = described_class.new(
        session_id: "session-123",
        source_format: :current,
        events: [ event ],
        message_snapshots: [],
        issues: [],
        source_paths: {}
      )

      expect(session.source_state).to eq(:complete)
      expect {
        described_class.new(
          session_id: "session-123",
          source_format: :current,
          source_state: :unknown,
          events: [ event ],
          message_snapshots: [],
          issues: [],
          source_paths: {}
        )
      }.to raise_error(ArgumentError, /source_state/)
    end
  end
end

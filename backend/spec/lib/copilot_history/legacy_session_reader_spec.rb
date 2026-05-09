require "rails_helper"

RSpec.describe CopilotHistory::LegacySessionReader, :copilot_history do
  describe "#call" do
    # 概要・目的: 「normalizes legacy timeline events and preserves chatMessages as message snapshots」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「normalizes legacy timeline events and preserves chatMessages as message
    #   snapshots」の条件・入力・操作を実行する。
    # 期待値: legacy timeline events and preserves chatMessages as message snapshots が正規化されること。
    it "normalizes legacy timeline events and preserves chatMessages as message snapshots" do
      with_copilot_history_fixture("legacy_valid") do |root|
        session = described_class.new.call(build_source(root, "legacy-valid"))

        expect(session.source_state).to eq(:complete)
        expect(session).to eq(
          CopilotHistory::Types::NormalizedSession.new(
            session_id: "legacy-valid",
            source_format: :legacy,
            cwd: nil,
            git_root: nil,
            repository: nil,
            branch: nil,
            created_at: "2026-04-26T08:00:00Z",
            updated_at: nil,
            selected_model: "gpt-5.4",
            events: [
              CopilotHistory::Types::NormalizedEvent.new(
                sequence: 1,
                kind: :message,
                raw_type: "user_message",
                occurred_at: "2026-04-26T08:00:01Z",
                role: "user",
                content: "show me recent sessions",
                raw_payload: {
                  "type" => "user_message",
                  "role" => "user",
                  "content" => "show me recent sessions",
                  "timestamp" => "2026-04-26T08:00:01Z"
                }
              ),
              CopilotHistory::Types::NormalizedEvent.new(
                sequence: 2,
                kind: :message,
                raw_type: "assistant_message",
                occurred_at: "2026-04-26T08:00:02Z",
                role: "assistant",
                content: "Here they are.",
                raw_payload: {
                  "type" => "assistant_message",
                  "role" => "assistant",
                  "content" => "Here they are.",
                  "timestamp" => "2026-04-26T08:00:02Z"
                }
              )
            ],
            message_snapshots: [
              CopilotHistory::Types::MessageSnapshot.new(
                role: "user",
                content: "show me recent sessions",
                raw_payload: {
                  "role" => "user",
                  "content" => "show me recent sessions"
                }
              ),
              CopilotHistory::Types::MessageSnapshot.new(
                role: "assistant",
                content: "Here they are.",
                raw_payload: {
                  "role" => "assistant",
                  "content" => "Here they are."
                }
              )
            ],
            issues: [],
            source_paths: {
              source: root.join("history-session-state/legacy-valid.json")
            }
          )
        )
      end
    end

    # 概要・目的: 「returns a session issue when the legacy source JSON cannot be parsed」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns a session issue when the legacy source JSON cannot be parsed」の条件・入力・操作を実行する。
    # 期待値: a session issue when the legacy source JSON cannot be parsed を返すこと。
    it "returns a session issue when the legacy source JSON cannot be parsed" do
      with_copilot_history_fixture("legacy_invalid") do |root|
        source_path = root.join("history-session-state/legacy-invalid.json")
        session = described_class.new.call(build_source(root, "legacy-invalid"))

        expect(session.session_id).to eq("legacy-invalid")
        expect(session.source_state).to eq(:degraded)
        expect(session.events).to eq([])
        expect(session.message_snapshots).to eq([])
        expect(session.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::LEGACY_JSON_PARSE_FAILED,
              message: "legacy session JSON could not be parsed",
              source_path: source_path,
              severity: :error
            )
          ]
        )
      end
    end

    # 概要・目的: 「returns a session issue when the legacy source file is unreadable」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns a session issue when the legacy source file is unreadable」の条件・入力・操作を実行する。
    # 期待値: a session issue when the legacy source file is unreadable を返すこと。
    it "returns a session issue when the legacy source file is unreadable" do
      with_copilot_history_fixture("legacy_unreadable") do |root|
        source_path = root.join("history-session-state/legacy-unreadable.json")

        with_permission_denied(source_path) do
          session = described_class.new.call(build_source(root, "legacy-unreadable"))

          expect(session.session_id).to eq("legacy-unreadable")
          expect(session.source_state).to eq(:degraded)
          expect(session.events).to eq([])
          expect(session.message_snapshots).to eq([])
          expect(session.issues).to eq(
            [
              CopilotHistory::Types::ReadIssue.new(
                code: CopilotHistory::Errors::ReadErrorCode::LEGACY_SOURCE_UNREADABLE,
                message: "legacy session source is not accessible",
                source_path: source_path,
                severity: :error
              )
            ]
          )
        end
      end
    end

    # 概要・目的: 「keeps unknown non-hash timeline entries as raw payload while preserving
    #   chatMessages」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「keeps unknown non-hash timeline entries as raw payload while preserving
    #   chatMessages」の条件・入力・操作を実行する。
    # 期待値: unknown non-hash timeline entries as raw payload while preserving chatMessages が維持されること。
    it "keeps unknown non-hash timeline entries as raw payload while preserving chatMessages" do
      with_copilot_history_fixture("legacy_valid") do |root|
        source_path = root.join("history-session-state/legacy-valid.json")
        payload = JSON.parse(source_path.read)
        payload["timeline"] << [ "mystery-event", { "value" => 9 } ]
        source_path.write(JSON.pretty_generate(payload))

        session = described_class.new.call(build_source(root, "legacy-valid"))

        expect(session.events.map(&:sequence)).to eq([ 1, 2, 3 ])
        expect(session.events.map(&:kind)).to eq([ :message, :message, :unknown ])
        expect(session.events.last.raw_payload).to eq([ "mystery-event", { "value" => 9 } ])
        expect(session.message_snapshots.size).to eq(2)
        expect(session.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
              message: "event payload could not be mapped to canonical fields",
              source_path: source_path,
              sequence: 3,
              severity: :warning
            )
          ]
        )
      end
    end

    def build_source(root, session_id)
      source_path = root.join("history-session-state/#{session_id}.json")

      CopilotHistory::Types::SessionSource.new(
        format: :legacy,
        session_id: session_id,
        source_path: source_path,
        artifact_paths: {
          source: source_path
        }
      )
    end
  end
end

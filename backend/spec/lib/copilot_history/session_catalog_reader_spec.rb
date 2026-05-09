require "rails_helper"

RSpec.describe CopilotHistory::SessionCatalogReader, :copilot_history do
  around do |example|
    original_copilot_home = ENV["COPILOT_HOME"]
    original_home = ENV["HOME"]

    example.run
  ensure
    ENV["COPILOT_HOME"] = original_copilot_home
    ENV["HOME"] = original_home
  end

  describe "#call" do
    # 概要・目的: 「returns a public success envelope with both current and legacy sessions」を通じて、HTTP
    #   レスポンスとエラー契約を検証する。
    # テストケース: 「returns a public success envelope with both current and legacy sessions」の条件・入力・操作を実行する。
    # 期待値: a public success envelope with both current and legacy sessions を返すこと。
    it "returns a public success envelope with both current and legacy sessions" do
      with_copilot_history_fixture("mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        result = build_reader.call

        expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
        expect(result.root).to eq(
          CopilotHistory::Types::ResolvedHistoryRoot.new(
            root_path: root,
            current_root: root.join("session-state"),
            legacy_root: root.join("history-session-state")
          )
        )
        expect(result.sessions.map(&:session_id)).to eq(%w[current-mixed legacy-mixed])
        expect(result.sessions.map(&:source_format)).to eq(%i[current legacy])
      end
    end

    # 概要・目的: 「returns current dotted schema and legacy sessions from the same history root」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「returns current dotted schema and legacy sessions from the same history root」の条件・入力・操作を実行する。
    # 期待値: current dotted schema and legacy sessions from the same history root を返すこと。
    it "returns current dotted schema and legacy sessions from the same history root" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        result = build_reader.call

        expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
        expect(result.sessions.map { |session| [ session.session_id, session.source_format, session.source_state ] }).to eq(
          [
            [ "current-schema-mixed", :current, :complete ],
            [ "legacy-schema-mixed", :legacy, :complete ]
          ]
        )
        expect(result.sessions.first.events.map(&:raw_type)).to eq(%w[user.message assistant.message])
        expect(result.sessions.last.events.map(&:raw_type)).to eq(%w[user_message assistant_message])
      end
    end

    # 概要・目的: 「preserves mixed-session ordering and raw payloads across current unknown and legacy partial
    #   events」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「preserves mixed-session ordering and raw payloads across current unknown and legacy partial
    #   events」の条件・入力・操作を実行する。
    # 期待値: mixed-session ordering が保持され、raw payloads across current unknown and legacy partial eventsこと。
    it "preserves mixed-session ordering and raw payloads across current unknown and legacy partial events" do
      with_copilot_history_fixture("mixed_root") do |root|
        legacy_path = root.join("history-session-state/legacy-mixed.json")
        legacy_payload = JSON.parse(legacy_path.read)
        legacy_payload["timeline"] << {
          "type" => "assistant_message",
          "role" => "assistant",
          "content" => "legacy partial event"
        }
        legacy_path.write(JSON.pretty_generate(legacy_payload))
        ENV["COPILOT_HOME"] = root.to_s

        result = build_reader.call

        expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)

        current_session = result.sessions.find { |session| session.session_id == "current-mixed" }
        legacy_session = result.sessions.find { |session| session.session_id == "legacy-mixed" }

        expect(current_session).to be_a(CopilotHistory::Types::NormalizedSession)
        expect(legacy_session).to be_a(CopilotHistory::Types::NormalizedSession)
        expect(result.root.root_path).to eq(root)
        expect(current_session.events.map(&:sequence)).to eq([ 1, 2 ])
        expect(current_session.events.last.kind).to eq(:unknown)
        expect(current_session.events.last.raw_payload).to eq(
          {
            "type" => "mystery-event",
            "payload" => { "value" => 42 },
            "timestamp" => "2026-04-26T10:00:02Z"
          }
        )
        expect(legacy_session.events.map(&:sequence)).to eq([ 1, 2 ])
        expect(legacy_session.events.last.kind).to eq(:message)
        expect(legacy_session.events.last.mapping_status).to eq(:partial)
        expect(legacy_session.events.last.raw_payload).to eq(
          {
            "type" => "assistant_message",
            "role" => "assistant",
            "content" => "legacy partial event"
          }
        )
        expect(legacy_session.issues).to include(
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
            message: "event payload matched partially",
            source_path: legacy_path,
            sequence: 2,
            severity: :warning
          )
        )
      end
    end

    # 概要・目的: 「keeps file-level session issues inside success results instead of promoting them to root
    #   failure」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「keeps file-level session issues inside success results instead of promoting them to root
    #   failure」の条件・入力・操作を実行する。
    # 期待値: file-level session issues inside success results instead of promoting them to root failure
    #   が維持されること。
    it "keeps file-level session issues inside success results instead of promoting them to root failure" do
      with_copilot_history_fixture("mixed_root") do |root|
        workspace_path = root.join("session-state/current-mixed/workspace.yaml")
        ENV["COPILOT_HOME"] = root.to_s

        with_permission_denied(workspace_path) do
          result = build_reader.call

          expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
          expect(result.sessions.map(&:session_id)).to eq(%w[current-mixed legacy-mixed])
          expect(result.sessions.find { |session| session.session_id == "current-mixed" }.issues).to include(
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_UNREADABLE,
              message: "workspace.yaml is not accessible",
              source_path: workspace_path,
              severity: :error
            )
          )
        end
      end
    end

    # 概要・目的: 「keeps parse and access failures scoped to sibling sessions without changing the public success
    #   envelope」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「keeps parse and access failures scoped to sibling sessions without changing the public success
    #   envelope」の条件・入力・操作を実行する。
    # 期待値: parse が維持され、access failures scoped to sibling sessions without changing the public success
    #   envelopeこと。
    it "keeps parse and access failures scoped to sibling sessions without changing the public success envelope" do
      with_copilot_history_fixture("mixed_root") do |root|
        events_path = root.join("session-state/current-mixed/events.jsonl")
        legacy_path = root.join("history-session-state/legacy-mixed.json")
        ENV["COPILOT_HOME"] = root.to_s
        events_path.write(<<~JSONL)
          {"type":"user_message","role":"user","content":"current survives","timestamp":"2026-04-26T10:00:01Z"}
          not-json
        JSONL

        with_permission_denied(legacy_path) do
          result = build_reader.call

          expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
          expect(result).not_to be_a(CopilotHistory::Types::ReadFailure)
          expect(result.sessions.map(&:session_id)).to eq(%w[current-mixed legacy-mixed])

          current_session = result.sessions.find { |session| session.session_id == "current-mixed" }
          legacy_session = result.sessions.find { |session| session.session_id == "legacy-mixed" }

          expect(current_session.events.map(&:sequence)).to eq([ 1 ])
          expect(current_session.issues).to include(
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
              message: "events.jsonl line could not be parsed",
              source_path: events_path,
              sequence: 2,
              severity: :error
            )
          )
          expect(legacy_session.events).to eq([])
          expect(legacy_session.issues).to include(
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::LEGACY_SOURCE_UNREADABLE,
              message: "legacy session source is not accessible",
              source_path: legacy_path,
              severity: :error
            )
          )
        end
      end
    end

    # 概要・目的: 「wraps fatal root failures in the public failure envelope and logs them as
    #   error」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「wraps fatal root failures in the public failure envelope and logs them as error」の条件・入力・操作を実行する。
    # 期待値: fatal root failures in the public failure envelope and logs them as error が公開用 envelope に包まれること。
    it "wraps fatal root failures in the public failure envelope and logs them as error" do
      logger = instance_double(Logger, warn: nil, error: nil)

      Dir.mktmpdir("copilot-history-home") do |home|
        expected_path = Pathname.new(home).join(".copilot")
        ENV.delete("COPILOT_HOME")
        ENV["HOME"] = home

        expect(logger).to receive(:error).with(
          hash_including(
            source_path: expected_path.to_s,
            failure_code: CopilotHistory::Errors::ReadErrorCode::ROOT_MISSING
          )
        )

        result = build_reader(logger: logger).call

        expect(result).to eq(
          CopilotHistory::Types::ReadResult::Failure.new(
            failure: CopilotHistory::Types::ReadFailure.new(
              code: CopilotHistory::Errors::ReadErrorCode::ROOT_MISSING,
              path: expected_path,
              message: "history root does not exist"
            )
          )
        )
      end
    end

    # 概要・目的: 「returns a public failure envelope when the resolved root exists but is not
    #   accessible」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「returns a public failure envelope when the resolved root exists but is not
    #   accessible」の条件・入力・操作を実行する。
    # 期待値: a public failure envelope when the resolved root exists but is not accessible を返すこと。
    it "returns a public failure envelope when the resolved root exists but is not accessible" do
      Dir.mktmpdir("copilot-history-home") do |home|
        expected_path = Pathname.new(home).join(".copilot")
        expected_path.mkdir
        ENV.delete("COPILOT_HOME")
        ENV["HOME"] = home

        with_permission_denied(expected_path) do
          result = build_reader.call

          expect(result).to be_a(CopilotHistory::Types::ReadResult::Failure)
          expect(result).not_to be_a(CopilotHistory::Types::ReadFailure)
          expect(result).to eq(
            CopilotHistory::Types::ReadResult::Failure.new(
              failure: CopilotHistory::Types::ReadFailure.new(
                code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
                path: expected_path,
                message: "history root is not accessible"
              )
            )
          )
        end
      end
    end

    # 概要・目的: 「wraps source catalog access failures in the public failure envelope」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「wraps source catalog access failures in the public failure envelope」の条件・入力・操作を実行する。
    # 期待値: source catalog access failures in the public failure envelope が公開用 envelope に包まれること。
    it "wraps source catalog access failures in the public failure envelope" do
      logger = instance_double(Logger, warn: nil, error: nil)

      with_copilot_history_fixture("current_valid") do |root|
        current_root = root.join("session-state")
        ENV["COPILOT_HOME"] = root.to_s

        expect(logger).to receive(:error).with(
          hash_including(
            source_path: current_root.to_s,
            failure_code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED
          )
        )

        with_permission_denied(current_root) do
          result = build_reader(logger: logger).call

          expect(result).to eq(
            CopilotHistory::Types::ReadResult::Failure.new(
              failure: CopilotHistory::Types::ReadFailure.new(
                code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
                path: current_root,
                message: "history source directory is not accessible"
              )
            )
          )
        end
      end
    end

    # 概要・目的: 「keeps session issues in the result without logging them」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps session issues in the result without logging them」の条件・入力・操作を実行する。
    # 期待値: session issues in the result without logging them が維持されること。
    it "keeps session issues in the result without logging them" do
      logger = instance_double(Logger, warn: nil, error: nil)

      with_copilot_history_fixture("mixed_root") do |root|
        workspace_path = root.join("session-state/current-mixed/workspace.yaml")
        ENV["COPILOT_HOME"] = root.to_s

        expect(logger).not_to receive(:warn)

        with_permission_denied(workspace_path) do
          result = build_reader(logger: logger).call

          expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
          expect(result.sessions.map(&:session_id)).to eq(%w[current-mixed legacy-mixed])
          expect(result.sessions.find { |session| session.session_id == "current-mixed" }.issues).to include(
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_UNREADABLE,
              message: "workspace.yaml is not accessible",
              source_path: workspace_path,
              severity: :error
            )
          )
        end
      end
    end

    # 概要・目的: 「does not log warning-only session issues while preserving them in the result」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「does not log warning-only session issues while preserving them in the result」の条件・入力・操作を実行する。
    # 期待値: log warning-only session issues while preserving them in the result しないこと。
    it "does not log warning-only session issues while preserving them in the result" do
      logger = instance_double(Logger, warn: nil, error: nil)

      with_copilot_history_fixture("mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        expect(logger).not_to receive(:warn)

        result = build_reader(logger: logger).call

        expect(result).to be_a(CopilotHistory::Types::ReadResult::Success)
        expect(result.sessions.flat_map(&:issues).map(&:code)).to include(
          CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE
        )
      end
    end

    def build_reader(logger: instance_double(Logger, warn: nil, error: nil))
      described_class.new(
        root_resolver: CopilotHistory::HistoryRootResolver.new(env: ENV),
        logger: logger
      )
    end
  end
end

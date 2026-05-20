require "rails_helper"

RSpec.describe CopilotHistory::CurrentSessionReader, :copilot_history do
  describe "#call" do
    # 概要・目的: 「builds one normalized session from workspace.yaml and events.jsonl」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「builds one normalized session from workspace.yaml and events.jsonl」の条件・入力・操作を実行する。
    # 期待値: one normalized session from workspace.yaml and events.jsonl が構築されること。
    it "builds one normalized session from workspace.yaml and events.jsonl" do
      with_copilot_history_fixture("current_valid") do |root|
        session = described_class.new.call(build_source(root, "current-valid"))

        expect(session).to eq(
          CopilotHistory::Types::NormalizedSession.new(
            session_id: "current-valid",
            source_format: :current,
            cwd: "/workspace/current-valid",
            git_root: "/workspace/current-valid",
            repository: "octo/example",
            branch: "main",
            created_at: "2026-04-26T09:00:00Z",
            updated_at: "2026-04-26T09:00:02Z",
            selected_model: nil,
            events: [
              CopilotHistory::Types::NormalizedEvent.new(
                sequence: 1,
                kind: :message,
                raw_type: "user_message",
                occurred_at: "2026-04-26T09:00:01Z",
                role: "user",
                content: "show recent sessions",
                raw_payload: {
                  "type" => "user_message",
                  "role" => "user",
                  "content" => "show recent sessions",
                  "timestamp" => "2026-04-26T09:00:01Z"
                }
              ),
              CopilotHistory::Types::NormalizedEvent.new(
                sequence: 2,
                kind: :message,
                raw_type: "assistant_message",
                occurred_at: "2026-04-26T09:00:02Z",
                role: "assistant",
                content: "Here are the latest sessions.",
                raw_payload: {
                  "type" => "assistant_message",
                  "role" => "assistant",
                  "content" => "Here are the latest sessions.",
                  "timestamp" => "2026-04-26T09:00:02Z"
                }
              )
            ],
            message_snapshots: [],
            issues: [],
            source_paths: {
              workspace: root.join("session-state/current-valid/workspace.yaml"),
              events: root.join("session-state/current-valid/events.jsonl")
            }
          )
        )
      end
    end

    # 概要・目的: 実運用の workspace.yaml と同じ unquoted timestamp を含む current session でも cwd metadata を失わない契約を検証する。
    # テストケース: created_at / updated_at を YAML timestamp として解釈される非引用値に書き換えた workspace.yaml を読む。
    # 期待値: workspace parse failed にせず、cwd / git_root / repository / branch と時刻 metadata を正規化できること。
    it "keeps workspace metadata when current workspace timestamps are unquoted YAML timestamps" do
      with_copilot_history_fixture("current_valid") do |root|
        workspace_path = root.join("session-state/current-valid/workspace.yaml")
        workspace_path.write(<<~YAML)
          session_id: current-valid
          cwd: /workspace/current-valid
          git_root: /workspace/current-valid
          repository: octo/example
          branch: main
          created_at: 2026-04-26T09:00:00Z
          updated_at: 2026-04-26T09:00:00Z
        YAML

        session = described_class.new.call(build_source(root, "current-valid"))

        expect(session.cwd.to_s).to eq("/workspace/current-valid")
        expect(session.git_root.to_s).to eq("/workspace/current-valid")
        expect(session.repository).to eq("octo/example")
        expect(session.branch).to eq("main")
        expect(session.created_at).to eq(Time.iso8601("2026-04-26T09:00:00Z"))
        expect(session.issues).not_to include(
          have_attributes(code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_PARSE_FAILED)
        )
      end
    end

    # 概要・目的: 「keeps readable events when workspace.yaml cannot be parsed」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps readable events when workspace.yaml cannot be parsed」の条件・入力・操作を実行する。
    # 期待値: readable events when workspace.yaml cannot be parsed が維持されること。
    it "keeps readable events when workspace.yaml cannot be parsed" do
      with_copilot_history_fixture("current_invalid_yaml") do |root|
        session = described_class.new.call(build_source(root, "current-invalid-yaml"))

        expect(session.session_id).to eq("current-invalid-yaml")
        expect(session.cwd).to be_nil
        expect(session.events).to eq(
          [
            CopilotHistory::Types::NormalizedEvent.new(
              sequence: 1,
              kind: :message,
              raw_type: "user_message",
              occurred_at: "2026-04-26T09:10:01Z",
              role: "user",
              content: "keep events readable",
              raw_payload: {
                "type" => "user_message",
                "role" => "user",
                "content" => "keep events readable",
                "timestamp" => "2026-04-26T09:10:01Z"
              }
            )
          ]
        )
        expect(session.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_PARSE_FAILED,
              message: "workspace.yaml could not be parsed",
              source_path: root.join("session-state/current-invalid-yaml/workspace.yaml"),
              severity: :error
            )
          ]
        )
      end
    end

    # 概要・目的: 「keeps readable lines and reports invalid JSONL lines and unknown events」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「keeps readable lines and reports invalid JSONL lines and unknown events」の条件・入力・操作を実行する。
    # 期待値: readable lines が維持され、reports invalid JSONL lines and unknown eventsこと。
    it "keeps readable lines and reports invalid JSONL lines and unknown events" do
      with_copilot_history_fixture("current_invalid_jsonl") do |root|
        session = described_class.new.call(build_source(root, "current-invalid-jsonl"))

        expect(session.events.map(&:sequence)).to eq([ 1, 3 ])
        expect(session.events.map(&:kind)).to eq(%i[message unknown])
        expect(session.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
              message: "events.jsonl line could not be parsed",
              source_path: root.join("session-state/current-invalid-jsonl/events.jsonl"),
              sequence: 2,
              severity: :error
            ),
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
              message: "event payload could not be mapped to canonical fields",
              source_path: root.join("session-state/current-invalid-jsonl/events.jsonl"),
              sequence: 3,
              severity: :warning
            )
          ]
        )
      end
    end

    # 概要・目的: 「keeps reading when a JSONL line parses into a non-hash payload」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps reading when a JSONL line parses into a non-hash payload」の条件・入力・操作を実行する。
    # 期待値: reading when a JSONL line parses into a non-hash payload が維持されること。
    it "keeps reading when a JSONL line parses into a non-hash payload" do
      with_copilot_history_fixture("current_valid") do |root|
        events_path = root.join("session-state/current-valid/events.jsonl")
        events_path.write(<<~JSONL)
          {"type":"user_message","role":"user","content":"show recent sessions","timestamp":"2026-04-26T09:00:01Z"}
          {"type":"assistant_message","role":"assistant","content":"Here are the latest sessions.","timestamp":"2026-04-26T09:00:02Z"}
          [1,2,3]
        JSONL

        session = described_class.new.call(build_source(root, "current-valid"))

        expect(session.events.map(&:sequence)).to eq([ 1, 2, 3 ])
        expect(session.events.last).to eq(
          CopilotHistory::Types::NormalizedEvent.new(
            sequence: 3,
            kind: :unknown,
            raw_type: "array",
            occurred_at: nil,
            role: nil,
            content: nil,
            raw_payload: [ 1, 2, 3 ]
          )
        )
        expect(session.issues).to include(
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
            message: "event payload could not be mapped to canonical fields",
            source_path: events_path,
            sequence: 3,
            severity: :warning
          )
        )
      end
    end

    # 概要・目的: 「falls back to events.jsonl mtime when readable current events do not contain
    #   timestamps」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「falls back to events.jsonl mtime when readable current events do not contain
    #   timestamps」の条件・入力・操作を実行する。
    # 期待値: events.jsonl mtime when readable current events do not contain timestamps に fallback すること。
    it "falls back to events.jsonl mtime when readable current events do not contain timestamps" do
      with_copilot_history_fixture("current_valid") do |root|
        events_path = root.join("session-state/current-valid/events.jsonl")
        events_path.write(<<~JSONL)
          {"type":"user_message","role":"user","content":"show recent sessions"}
          {"type":"assistant_message","role":"assistant","content":"Here are the latest sessions."}
        JSONL
        File.utime(Time.utc(2026, 4, 26, 9, 3, 0), Time.utc(2026, 4, 26, 9, 3, 0), events_path)

        session = described_class.new.call(build_source(root, "current-valid"))

        expect(session.updated_at).to eq(Time.iso8601("2026-04-26T09:03:00Z"))
        expect(session.source_state).to eq(:degraded)
        expect(session.events.map(&:sequence)).to eq([ 1, 2 ])
      end
    end

    # 概要・目的: 「returns a session issue when workspace.yaml is unreadable but still keeps readable
    #   events」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「returns a session issue when workspace.yaml is unreadable but still keeps readable
    #   events」の条件・入力・操作を実行する。
    # 期待値: a session issue when workspace.yaml is unreadable but still keeps readable events を返すこと。
    it "returns a session issue when workspace.yaml is unreadable but still keeps readable events" do
      with_copilot_history_fixture("current_unreadable") do |root|
        workspace_path = root.join("session-state/current-unreadable/workspace.yaml")

        with_permission_denied(workspace_path) do
          session = described_class.new.call(build_source(root, "current-unreadable"))

          expect(session.session_id).to eq("current-unreadable")
          expect(session.cwd).to be_nil
          expect(session.events.size).to eq(1)
          expect(session.issues).to eq(
            [
              CopilotHistory::Types::ReadIssue.new(
                code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_UNREADABLE,
                message: "workspace.yaml is not accessible",
                source_path: workspace_path,
                severity: :error
              )
            ]
          )
        end
      end
    end

    # 概要・目的: 「returns a session issue when events.jsonl is unreadable while keeping workspace
    #   metadata」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「returns a session issue when events.jsonl is unreadable while keeping workspace
    #   metadata」の条件・入力・操作を実行する。
    # 期待値: a session issue when events.jsonl is unreadable while keeping workspace metadata を返すこと。
    it "returns a session issue when events.jsonl is unreadable while keeping workspace metadata" do
      with_copilot_history_fixture("current_unreadable") do |root|
        events_path = root.join("session-state/current-unreadable/events.jsonl")

        with_permission_denied(events_path) do
          session = described_class.new.call(build_source(root, "current-unreadable"))

          expect(session.session_id).to eq("current-unreadable")
          expect(session.cwd).to eq(Pathname("/workspace/current-unreadable"))
          expect(session.events).to eq([])
          expect(session.issues).to eq(
            [
              CopilotHistory::Types::ReadIssue.new(
                code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_UNREADABLE,
                message: "events.jsonl is not accessible",
                source_path: events_path,
                severity: :error
              )
            ]
          )
        end
      end
    end

    # 概要・目的: 「normalizes current dotted schema fixtures into message, detail, and unknown events with helper
    #   fields」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「normalizes current dotted schema fixtures into message, detail, and unknown events with helper
    #   fields」の条件・入力・操作を実行する。
    # 期待値: current dotted schema fixtures into message, detail, and unknown events with helper fields
    #   が正規化されること。
    it "normalizes current dotted schema fixtures into message, detail, and unknown events with helper fields" do
      with_copilot_history_fixture("current_schema_valid") do |root|
        session = described_class.new.call(build_source(root, "current-schema-valid"))

        expect(session.source_state).to eq(:complete)
        expect(session.updated_at).to eq(Time.iso8601("2026-04-28T01:00:09Z"))
        expect(session.events.map { |event| [ event.sequence, event.kind, event.mapping_status, event.raw_type ] }).to eq(
          [
            [ 1, :message, :complete, "system.message" ],
            [ 2, :message, :complete, "user.message" ],
            [ 3, :detail, :complete, "assistant.turn_start" ],
            [ 4, :message, :complete, "assistant.message" ],
            [ 5, :message, :complete, "assistant.message" ],
            [ 6, :detail, :complete, "tool.execution_start" ],
            [ 7, :detail, :complete, "tool.execution_complete" ],
            [ 8, :detail, :complete, "skill.invoked" ],
            [ 9, :detail, :complete, "assistant.turn_end" ]
          ]
        )
        expect(session.events.fetch(3).tool_calls).to eq(
          [
            CopilotHistory::Types::NormalizedToolCall.new(
              name: "functions.bash",
              arguments_preview: "{\"command\":\"git --no-pager status\",\"description\":\"Inspect repository status\"}",
              is_truncated: false,
              status: :complete
            )
          ]
        )
        expect(session.events.fetch(4).content).to be_nil
        expect(session.events.fetch(4).tool_calls).to eq(
          [
            CopilotHistory::Types::NormalizedToolCall.new(
              name: "functions.bash",
              arguments_preview: "{\"command\":\"pwd\"}",
              is_truncated: false,
              status: :complete
            )
          ]
        )
        expect(session.events.fetch(7).detail).to eq(
          category: "skill",
          title: "skill.invoked",
          body: "kiro-review / functions.skill"
        )
        expect(session.events.fetch(2).detail).to eq(
          category: "assistant_turn",
          title: "assistant.turn_start",
          body: "turn-1"
        )
        expect(session.issues).to eq([])
      end
    end

    # 概要・目的: 「keeps readable current dotted events while surfacing partial tool summaries, unknown events, and
    #   invalid jsonl lines」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「keeps readable current dotted events while surfacing partial tool summaries, unknown events,
    #   and invalid jsonl lines」の条件・入力・操作を実行する。
    # 期待値: readable current dotted events while surfacing partial tool summaries, unknown events,
    #   が維持され、invalid jsonl linesこと。
    it "keeps readable current dotted events while surfacing partial tool summaries, unknown events, and invalid jsonl lines" do
      with_copilot_history_fixture("current_schema_degraded") do |root|
        session = described_class.new.call(build_source(root, "current-schema-degraded"))

        expect(session.source_state).to eq(:degraded)
        expect(session.updated_at).to eq(Time.iso8601("2026-04-28T02:00:04Z"))
        expect(session.events.map { |event| [ event.sequence, event.kind, event.mapping_status, event.raw_type ] }).to eq(
          [
            [ 1, :message, :complete, "user.message" ],
            [ 2, :message, :partial, "assistant.message" ],
            [ 3, :detail, :complete, "hook.start" ],
            [ 4, :unknown, :complete, "mystery.event" ]
          ]
        )
        expect(session.events.fetch(1).tool_calls).to eq(
          [
            CopilotHistory::Types::NormalizedToolCall.new(
              name: nil,
              arguments_preview: "{\"command\":\"printenv\",\"token\":\"[REDACTED]\"}",
              is_truncated: false,
              status: :partial
            )
          ]
        )
        expect(session.events.fetch(2).detail).to eq(
          category: "hook",
          title: "hook.start",
          body: "before-tool / *"
        )
        expect(session.issues).to include(
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
            message: "event payload matched partially",
            source_path: root.join("session-state/current-schema-degraded/events.jsonl"),
            sequence: 2,
            severity: :warning
          ),
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::EVENT_UNKNOWN_SHAPE,
            message: "event payload could not be mapped to canonical fields",
            source_path: root.join("session-state/current-schema-degraded/events.jsonl"),
            sequence: 4,
            severity: :warning
          ),
          CopilotHistory::Types::ReadIssue.new(
            code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
            message: "events.jsonl line could not be parsed",
            source_path: root.join("session-state/current-schema-degraded/events.jsonl"),
            sequence: 5,
            severity: :error
          )
        )
      end
    end

    # 概要・目的: 「marks workspace-only current sessions with a dedicated issue when events.jsonl is
    #   missing」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「marks workspace-only current sessions with a dedicated issue when events.jsonl is
    #   missing」の条件・入力・操作を実行する。
    # 期待値: 「marks workspace-only current sessions with a dedicated issue when events.jsonl is
    #   missing」で示す状態または振る舞いが成立すること。
    it "marks workspace-only current sessions with a dedicated issue when events.jsonl is missing" do
      with_copilot_history_fixture("current_schema_workspace_only") do |root|
        session = described_class.new.call(build_source(root, "current-schema-workspace-only"))

        expect(session.session_id).to eq("current-schema-workspace-only")
        expect(session.source_state).to eq(:workspace_only)
        expect(session.updated_at).to eq(Time.iso8601("2026-04-28T03:01:00Z"))
        expect(session.events).to eq([])
        expect(session.issues).to eq(
          [
            CopilotHistory::Types::ReadIssue.new(
              code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_MISSING,
              message: "events.jsonl is missing for current session",
              source_path: root.join("session-state/current-schema-workspace-only/events.jsonl"),
              severity: :warning
            )
          ]
        )
      end
    end

    # 概要・目的: 「extracts selected_model from the shared current model fixture and ignores lower-priority later
    #   candidates」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「extracts selected_model from the shared current model fixture and ignores lower-priority later
    #   candidates」の条件・入力・操作を実行する。
    # 期待値: 「extracts selected_model from the shared current model fixture and ignores lower-priority later
    #   candidates」で示す状態または振る舞いが成立すること。
    it "extracts selected_model from the shared current model fixture and ignores lower-priority later candidates" do
      with_copilot_history_fixture("current_model") do |root|
        with_model_session = described_class.new.call(build_source(root, "current-model-with-values"))

        expect(with_model_session.selected_model).to eq("gpt-5-current")
      end
    end

    # 概要・目的: 「falls back to tool.execution_complete data.model when shutdown currentModel is
    #   unavailable」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「falls back to tool.execution_complete data.model when shutdown currentModel is
    #   unavailable」の条件・入力・操作を実行する。
    # 期待値: tool.execution_complete data.model when shutdown currentModel is unavailable に fallback すること。
    it "falls back to tool.execution_complete data.model when shutdown currentModel is unavailable" do
      with_copilot_history_fixture("current_model") do |root|
        session = described_class.new.call(build_source(root, "current-model-tool-fallback"))

        expect(session.selected_model).to eq("gpt-5-tool-fallback")
      end
    end

    # 概要・目的: 「uses the later non-empty model candidate within the same priority」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「uses the later non-empty model candidate within the same priority」の条件・入力・操作を実行する。
    # 期待値: the later non-empty model candidate within the same priority が使われること。
    it "uses the later non-empty model candidate within the same priority" do
      with_copilot_history_fixture("current_model") do |root|
        session = described_class.new.call(build_source(root, "current-model-same-priority-later"))

        expect(session.selected_model).to eq("gpt-5-tool-later")
      end
    end

    # 概要・目的: 「trims confirmed model candidates before storing selected_model」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「trims confirmed model candidates before storing selected_model」の条件・入力・操作を実行する。
    # 期待値: 「trims confirmed model candidates before storing selected_model」で示す状態または振る舞いが成立すること。
    it "trims confirmed model candidates before storing selected_model" do
      with_copilot_history_fixture("current_model") do |root|
        session = described_class.new.call(build_source(root, "current-model-trimmed"))

        expect(session.selected_model).to eq("gpt-5-trimmed")
      end
    end

    # 概要・目的: 「prefers saved assistant.usage data.model over a root model when higher-priority candidates are
    #   unavailable」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「prefers saved assistant.usage data.model over a root model when higher-priority candidates are
    #   unavailable」の条件・入力・操作を実行する。
    # 期待値: 「prefers saved assistant.usage data.model over a root model when higher-priority candidates are
    #   unavailable」で示す状態または振る舞いが成立すること。
    it "prefers saved assistant.usage data.model over a root model when higher-priority candidates are unavailable" do
      with_copilot_history_fixture("current_model") do |root|
        session = described_class.new.call(build_source(root, "current-model-usage-fallback"))

        expect(session.selected_model).to eq("gpt-5-usage-fallback")
      end
    end

    # 概要・目的: 「falls back to a saved root model when higher-priority candidates are unavailable」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「falls back to a saved root model when higher-priority candidates are
    #   unavailable」の条件・入力・操作を実行する。
    # 期待値: a saved root model when higher-priority candidates are unavailable に fallback すること。
    it "falls back to a saved root model when higher-priority candidates are unavailable" do
      with_copilot_history_fixture("current_model") do |root|
        session = described_class.new.call(build_source(root, "current-model-root-fallback"))

        expect(session.selected_model).to eq("gpt-5-root-fallback")
      end
    end

    # 概要・目的: 「returns nil when the current model fixture has only missing or unusable candidates」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「returns nil when the current model fixture has only missing or unusable
    #   candidates」の条件・入力・操作を実行する。
    # 期待値: nil when the current model fixture has only missing or unusable candidates を返すこと。
    it "returns nil when the current model fixture has only missing or unusable candidates" do
      with_copilot_history_fixture("current_model") do |root|
        without_model_session = described_class.new.call(build_source(root, "current-model-without-values"))

        expect(without_model_session.selected_model).to be_nil
      end
    end

    def build_source(root, session_id)
      source_path = root.join("session-state", session_id)

      CopilotHistory::Types::SessionSource.new(
        format: :current,
        session_id: session_id,
        source_path: source_path,
        artifact_paths: {
          workspace: source_path.join("workspace.yaml"),
          events: source_path.join("events.jsonl")
        }
      )
    end
  end
end

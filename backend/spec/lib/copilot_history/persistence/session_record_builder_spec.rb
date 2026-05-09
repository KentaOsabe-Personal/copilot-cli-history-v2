require "rails_helper"

RSpec.describe CopilotHistory::Persistence::SessionRecordBuilder do
  around do |example|
    Dir.mktmpdir("session-record-builder") do |dir|
      @tmpdir = Pathname.new(dir)
      example.run
    end
  end

  describe "#call" do
    # 概要・目的: 「reuses existing presenter payloads as summary and detail snapshots without raw
    #   payloads」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「reuses existing presenter payloads as summary and detail snapshots without raw
    #   payloads」の条件・入力・操作を実行する。
    # 期待値: 「reuses existing presenter payloads as summary and detail snapshots without raw
    #   payloads」で示す状態または振る舞いが成立すること。
    it "reuses existing presenter payloads as summary and detail snapshots without raw payloads" do
      events_path = write_source("current/events.jsonl", "{\"type\":\"assistant.message\"}\n")
      workspace_path = write_source("current/workspace.yaml", "cwd: /workspace/current\n")
      session = build_session(
        session_id: "current-session",
        source_format: :current,
        source_state: :complete,
        created_at: "2026-04-28T01:00:00Z",
        updated_at: "2026-04-28T01:02:00Z",
        source_paths: {
          workspace: workspace_path,
          events: events_path
        },
        events: [
          build_event(
            sequence: 1,
            raw_type: "assistant.message",
            occurred_at: "2026-04-28T01:00:04Z",
            role: "assistant",
            content: "I can inspect sessions.",
            raw_payload: { "type" => "assistant.message", "content" => "raw should stay out" }
          )
        ]
      )

      attributes = described_class.new.call(session:, indexed_at: Time.zone.parse("2026-04-30 12:00:00"))

      expect(attributes.fetch(:summary_payload)).to include(
        id: "current-session",
        source_format: "current",
        conversation_summary: {
          has_conversation: true,
          message_count: 1,
          preview: "I can inspect sessions.",
          activity_count: 0
        },
        degraded: false
      )
      expect(attributes.fetch(:detail_payload)).to include(
        id: "current-session",
        raw_included: false,
        conversation: include(message_count: 1),
        timeline: [
          include(
            sequence: 1,
            raw_payload: nil
          )
        ]
      )
    end

    # 概要・目的: 「maps session scalars, source metadata, counts, and source dates into valid read model
    #   attributes」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「maps session scalars, source metadata, counts, and source dates into valid read model
    #   attributes」の条件・入力・操作を実行する。
    # 期待値: 「maps session scalars, source metadata, counts, and source dates into valid read model
    #   attributes」で示す状態または振る舞いが成立すること。
    it "maps session scalars, source metadata, counts, and source dates into valid read model attributes" do
      events_path = write_source("current/events.jsonl", "{}\n")
      workspace_path = write_source("current/workspace.yaml", "cwd: /workspace/current\n")
      issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "event payload matched partially",
        source_path: events_path,
        sequence: 2,
        severity: :warning
      )
      indexed_at = Time.zone.parse("2026-04-30 12:00:00")
      session = build_session(
        session_id: "degraded-current",
        source_format: :current,
        source_state: :degraded,
        cwd: "/workspace/current",
        git_root: "/workspace/current",
        repository: "octo/example",
        branch: "feature/history-db",
        created_at: "2026-04-28T01:00:00Z",
        updated_at: "2026-04-28T01:02:00Z",
        selected_model: "gpt-5-current",
        source_paths: {
          workspace: workspace_path,
          events: events_path
        },
        events: [
          build_event(sequence: 1, raw_type: "user.message", occurred_at: "2026-04-28T01:00:01Z", role: "user", content: "hello"),
          build_event(sequence: 2, raw_type: "assistant.message", occurred_at: "2026-04-28T01:00:02Z", role: "assistant", content: "hi")
        ],
        message_snapshots: [
          CopilotHistory::Types::MessageSnapshot.new(role: "assistant", content: "hi", raw_payload: { "content" => "hi" })
        ],
        issues: [ issue ]
      )

      attributes = described_class.new.call(session:, indexed_at:)

      expect(attributes).to include(
        session_id: "degraded-current",
        source_format: "current",
        source_state: "degraded",
        created_at_source: Time.iso8601("2026-04-28T01:00:00Z"),
        updated_at_source: Time.iso8601("2026-04-28T01:02:00Z"),
        cwd: "/workspace/current",
        git_root: "/workspace/current",
        repository: "octo/example",
        branch: "feature/history-db",
        selected_model: "gpt-5-current",
        event_count: 2,
        message_snapshot_count: 1,
        issue_count: 1,
        degraded: true,
        conversation_preview: "hello",
        search_text: include("hello", "hi", "event payload matched partially"),
        search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION,
        message_count: 2,
        activity_count: 0,
        source_paths: {
          "workspace" => workspace_path.to_s,
          "events" => events_path.to_s
        },
        indexed_at: indexed_at
      )
      expect(attributes.fetch(:source_fingerprint)).to include(
        "complete" => true,
        "artifacts" => include(
          "workspace" => include("path" => workspace_path.to_s, "status" => "ok"),
          "events" => include("path" => events_path.to_s, "status" => "ok")
        )
      )
      expect(attributes.fetch(:search_text)).not_to include(
        "/workspace/current",
        "octo/example",
        "feature/history-db",
        "gpt-5-current"
      )
      expect(CopilotSession.new(attributes)).to be_valid
    end

    # 概要・目的: 「builds search text from presenter conversation payloads without tool or scalar metadata
    #   noise」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「builds search text from presenter conversation payloads without tool or scalar metadata
    #   noise」の条件・入力・操作を実行する。
    # 期待値: search text from presenter conversation payloads without tool or scalar metadata noise が構築されること。
    it "builds search text from presenter conversation payloads without tool or scalar metadata noise" do
      source_path = write_source("current/events.jsonl", "{}\n")
      session = build_session(
        session_id: "searchable-session",
        source_format: :current,
        cwd: "/workspace/searchable",
        repository: "octo/searchable",
        selected_model: "gpt-5-search",
        source_paths: { events: source_path },
        events: [
          build_event(
            sequence: 1,
            raw_type: "assistant.message",
            occurred_at: "2026-04-28T01:00:00Z",
            role: "assistant",
            content: "Use ripgrep to find migration errors",
            tool_calls: [
              {
                name: "shell",
                arguments_preview: "rg migration",
                is_truncated: false,
                status: :complete
              }
            ]
          )
        ]
      )

      attributes = described_class.new.call(session:, indexed_at: Time.zone.parse("2026-04-30 12:00:00"))

      expect(attributes.fetch(:search_text)).to include(
        "Use ripgrep to find migration errors"
      )
      expect(attributes.fetch(:search_text)).not_to include(
        "shell",
        "rg migration",
        "/workspace/searchable",
        "octo/searchable",
        "gpt-5-search"
      )
      expect(attributes.fetch(:search_text_version)).to eq(CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION)
    end

    # 概要・目的: 「preserves missing history dates and maps legacy sessions through the shared contract」を通じて、reader
    #   と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「preserves missing history dates and maps legacy sessions through the shared
    #   contract」の条件・入力・操作を実行する。
    # 期待値: missing history dates が保持され、maps legacy sessions through the shared contractこと。
    it "preserves missing history dates and maps legacy sessions through the shared contract" do
      source_path = write_source("legacy/session.json", "{}")
      session = build_session(
        session_id: "legacy-session",
        source_format: :legacy,
        source_state: :complete,
        created_at: nil,
        updated_at: nil,
        selected_model: "gpt-5.4",
        source_paths: {
          source: source_path
        },
        events: [
          build_event(sequence: 1, raw_type: "assistant_message", occurred_at: nil, role: "assistant", content: "legacy answer")
        ]
      )

      attributes = described_class.new.call(session:, indexed_at: Time.zone.parse("2026-04-30 12:00:00"))

      expect(attributes).to include(
        session_id: "legacy-session",
        source_format: "legacy",
        source_state: "complete",
        created_at_source: nil,
        updated_at_source: nil,
        selected_model: "gpt-5.4",
        source_paths: {
          "source" => source_path.to_s
        },
        conversation_preview: "legacy answer",
        message_count: 1
      )
      expect(attributes.fetch(:summary_payload)).to include(
        id: "legacy-session",
        source_format: "legacy",
        created_at: nil,
        updated_at: nil
      )
      expect(CopilotSession.new(attributes)).to be_valid
    end

    # 概要・目的: 「returns replaceable attributes and does not persist records or make sync decisions」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns replaceable attributes and does not persist records or make sync
    #   decisions」の条件・入力・操作を実行する。
    # 期待値: replaceable attributes and does not persist records or make sync decisions を返すこと。
    it "returns replaceable attributes and does not persist records or make sync decisions" do
      source_path = write_source("current/events.jsonl", "{}\n")
      indexed_at = Time.zone.parse("2026-04-30 12:00:00")
      original = build_session(
        session_id: "replaceable-session",
        source_format: :current,
        updated_at: "2026-04-28T01:00:00Z",
        source_paths: { events: source_path },
        events: [
          build_event(sequence: 1, raw_type: "user.message", occurred_at: "2026-04-28T01:00:00Z", role: "user", content: "first")
        ]
      )
      regenerated = build_session(
        session_id: "replaceable-session",
        source_format: :current,
        updated_at: "2026-04-28T01:05:00Z",
        source_paths: { events: source_path },
        events: [
          build_event(sequence: 1, raw_type: "user.message", occurred_at: "2026-04-28T01:05:00Z", role: "user", content: "updated")
        ]
      )

      original_attributes = described_class.new.call(session: original, indexed_at:)
      regenerated_attributes = described_class.new.call(session: regenerated, indexed_at:)

      expect(original_attributes.fetch(:session_id)).to eq(regenerated_attributes.fetch(:session_id))
      expect(regenerated_attributes.fetch(:summary_payload)).not_to eq(original_attributes.fetch(:summary_payload))
      expect(regenerated_attributes.fetch(:conversation_preview)).to eq("updated")
      expect(regenerated_attributes.fetch(:search_text)).to include("updated")
      expect(CopilotSession.where(session_id: "replaceable-session")).not_to exist
      expect(regenerated_attributes.keys).not_to include(:skip, :upsert, :delete, :raw_files_primary_source)
    end

    # 概要・目的: 「uses a precomputed source fingerprint when provided」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「uses a precomputed source fingerprint when provided」の条件・入力・操作を実行する。
    # 期待値: a precomputed source fingerprint when provided が使われること。
    it "uses a precomputed source fingerprint when provided" do
      source_path = write_source("current/events.jsonl", "{}\n")
      precomputed_fingerprint = {
        "complete" => true,
        "artifacts" => {
          "events" => {
            "path" => source_path.to_s,
            "mtime" => "2026-04-30T00:00:00Z",
            "size" => 3,
            "status" => "ok"
          }
        }
      }
      fingerprint_builder = instance_double(
        CopilotHistory::Persistence::SourceFingerprintBuilder,
        call: { "complete" => false, "artifacts" => {} }
      )
      session = build_session(
        session_id: "precomputed-fingerprint-session",
        source_format: :current,
        source_paths: { events: source_path },
        events: [
          build_event(sequence: 1, raw_type: "user.message", occurred_at: "2026-04-28T01:00:00Z", role: "user", content: "hello")
        ]
      )

      attributes = described_class.new(fingerprint_builder:).call(
        session:,
        indexed_at: Time.zone.parse("2026-04-30 12:00:00"),
        source_fingerprint: precomputed_fingerprint
      )

      expect(attributes.fetch(:source_fingerprint)).to eq(precomputed_fingerprint)
      expect(fingerprint_builder).not_to have_received(:call)
    end

    # 概要・目的: 「computes the source fingerprint when none is provided」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「computes the source fingerprint when none is provided」の条件・入力・操作を実行する。
    # 期待値: 「computes the source fingerprint when none is provided」で示す状態または振る舞いが成立すること。
    it "computes the source fingerprint when none is provided" do
      source_path = write_source("current/events.jsonl", "{}\n")
      computed_fingerprint = { "complete" => true, "artifacts" => { "events" => { "status" => "ok" } } }
      fingerprint_builder = instance_double(
        CopilotHistory::Persistence::SourceFingerprintBuilder,
        call: computed_fingerprint
      )
      session = build_session(
        session_id: "computed-fingerprint-session",
        source_format: :current,
        source_paths: { events: source_path },
        events: [
          build_event(sequence: 1, raw_type: "user.message", occurred_at: "2026-04-28T01:00:00Z", role: "user", content: "hello")
        ]
      )

      attributes = described_class.new(fingerprint_builder:).call(
        session:,
        indexed_at: Time.zone.parse("2026-04-30 12:00:00")
      )

      expect(attributes.fetch(:source_fingerprint)).to eq(computed_fingerprint)
      expect(fingerprint_builder).to have_received(:call).with(source_paths: session.source_paths)
    end
  end

  def write_source(relative_path, content)
    path = @tmpdir.join(relative_path)
    path.dirname.mkpath
    path.write(content)
    path
  end

  def build_session(
    session_id:,
    source_format:,
    source_state: :complete,
    cwd: nil,
    git_root: nil,
    repository: nil,
    branch: nil,
    created_at: "2026-04-28T01:00:00Z",
    updated_at: nil,
    selected_model: nil,
    events: [],
    message_snapshots: [],
    issues: [],
    source_paths:
  )
    CopilotHistory::Types::NormalizedSession.new(
      session_id:,
      source_format:,
      source_state:,
      cwd:,
      git_root:,
      repository:,
      branch:,
      created_at:,
      updated_at:,
      selected_model:,
      events:,
      message_snapshots:,
      issues:,
      source_paths:
    )
  end

  def build_event(sequence:, raw_type:, occurred_at:, role:, content:, kind: :message, raw_payload: {}, tool_calls: [])
    CopilotHistory::Types::NormalizedEvent.new(
      sequence:,
      kind:,
      raw_type:,
      occurred_at:,
      role:,
      content:,
      tool_calls:,
      raw_payload:
    )
  end
end

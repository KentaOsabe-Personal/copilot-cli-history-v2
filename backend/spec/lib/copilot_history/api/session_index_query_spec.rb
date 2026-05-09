require "rails_helper"

RSpec.describe CopilotHistory::Api::SessionIndexQuery do
  subject(:query) { described_class.new }

  describe "#call" do
    it "returns stored summary payloads without reconstructing fields for current and legacy sessions" do
      create_session(
        session_id: "current-session",
        source_format: "current",
        updated_at_source: "2026-04-26T10:00:00Z",
        summary_payload: {
          "id" => "current-session",
          "source_format" => "current",
          "source_state" => "complete",
          "workspace" => { "cwd" => "/work/current" },
          "model" => "gpt-5",
          "conversation_summary" => "current summary",
          "degraded" => false,
          "issues" => []
        }
      )
      create_session(
        session_id: "legacy-session",
        source_format: "legacy",
        updated_at_source: "2026-04-25T10:00:00Z",
        summary_payload: {
          "id" => "legacy-session",
          "source_format" => "legacy",
          "source_state" => "workspace_only",
          "workspace" => { "cwd" => "/work/legacy" },
          "model" => nil,
          "conversation_summary" => "legacy summary",
          "degraded" => true,
          "issues" => [ { "code" => "legacy_issue" } ]
        }
      )

      result = query.call(
        from_time: Time.zone.parse("2026-04-01T00:00:00Z"),
        to_time: Time.zone.parse("2026-04-30T23:59:59Z")
      )

      expect(result).to be_a(CopilotHistory::Api::Types::SessionIndexResult::Success)
      expect(result.data).to eq(
        [
          {
            "id" => "current-session",
            "source_format" => "current",
            "source_state" => "complete",
            "workspace" => { "cwd" => "/work/current" },
            "model" => "gpt-5",
            "conversation_summary" => "current summary",
            "degraded" => false,
            "issues" => []
          },
          {
            "id" => "legacy-session",
            "source_format" => "legacy",
            "source_state" => "workspace_only",
            "workspace" => { "cwd" => "/work/legacy" },
            "model" => nil,
            "conversation_summary" => "legacy summary",
            "degraded" => true,
            "issues" => [ { "code" => "legacy_issue" } ]
          }
        ]
      )
      expect(result.meta).to eq({ count: 2, partial_results: true })
    end

    it "uses updated source time before created source time and excludes rows without display time" do
      create_session(
        session_id: "uses-updated",
        created_at_source: "2026-01-01T00:00:00Z",
        updated_at_source: "2026-04-20T09:00:00Z"
      )
      create_session(
        session_id: "uses-created",
        created_at_source: "2026-04-20T08:00:00Z",
        updated_at_source: nil
      )
      create_session(
        session_id: "outside-created",
        created_at_source: "2026-03-31T23:59:59Z",
        updated_at_source: nil
      )
      create_session(
        session_id: "missing-display-time",
        created_at_source: nil,
        updated_at_source: nil
      )

      result = query.call(
        from_time: Time.zone.parse("2026-04-01T00:00:00Z"),
        to_time: Time.zone.parse("2026-04-30T23:59:59Z")
      )

      expect(result.data.map { |payload| payload["id"] }).to eq(%w[uses-updated uses-created])
      expect(result.meta).to eq({ count: 2, partial_results: false })
    end

    it "sorts by display time descending and session id ascending before applying limit" do
      create_session(session_id: "same-b", updated_at_source: "2026-04-26T10:00:00Z")
      create_session(session_id: "latest", updated_at_source: "2026-04-27T10:00:00Z")
      create_session(session_id: "same-a", updated_at_source: "2026-04-26T10:00:00Z")
      create_session(session_id: "oldest", updated_at_source: "2026-04-25T10:00:00Z")

      result = query.call(
        from_time: Time.zone.parse("2026-04-01T00:00:00Z"),
        to_time: Time.zone.parse("2026-04-30T23:59:59Z"),
        limit: 3
      )

      expect(result.data.map { |payload| payload["id"] }).to eq(%w[latest same-a same-b])
      expect(result.meta).to eq({ count: 3, partial_results: false })
    end

    it "does not ask MySQL to sort rows that include JSON payload columns" do
      create_session(session_id: "same-b", updated_at_source: "2026-04-26T10:00:00Z")
      create_session(session_id: "same-a", updated_at_source: "2026-04-26T10:00:00Z")

      sql_statements = []
      subscriber = lambda do |_name, _started, _finished, _unique_id, payload|
        sql = payload[:sql]
        sql_statements << sql if sql.match?(/\ASELECT .*copilot_sessions/i)
      end

      ActiveSupport::Notifications.subscribed(subscriber, "sql.active_record") do
        query.call(
          from_time: Time.zone.parse("2026-04-01T00:00:00Z"),
          to_time: Time.zone.parse("2026-04-30T23:59:59Z")
        )
      end

      expect(sql_statements).not_to include(match(/ORDER BY COALESCE/i))
    end

    it "supports one-sided ranges and returns an empty success when no rows match" do
      create_session(session_id: "before", updated_at_source: "2026-04-01T00:00:00Z")
      create_session(session_id: "after", updated_at_source: "2026-05-01T00:00:00Z")

      from_result = query.call(from_time: Time.zone.parse("2026-04-15T00:00:00Z"))
      to_result = query.call(to_time: Time.zone.parse("2026-04-15T00:00:00Z"))
      empty_result = query.call(
        from_time: Time.zone.parse("2026-06-01T00:00:00Z"),
        to_time: Time.zone.parse("2026-06-30T23:59:59Z")
      )

      expect(from_result.data.map { |payload| payload["id"] }).to eq(%w[after])
      expect(to_result.data.map { |payload| payload["id"] }).to eq(%w[before])
      expect(empty_result).to eq(
        CopilotHistory::Api::Types::SessionIndexResult::Success.new(
          data: [],
          meta: { count: 0, partial_results: false }
        )
      )
    end
  end

  def create_session(session_id:, source_format: "current", created_at_source: nil, updated_at_source: nil, summary_payload: nil)
    CopilotSession.create!(
      session_id: session_id,
      source_format: source_format,
      source_state: "complete",
      created_at_source: parse_time(created_at_source),
      updated_at_source: parse_time(updated_at_source),
      cwd: "/work/#{session_id}",
      git_root: "/work/#{session_id}",
      repository: "example/repo",
      branch: "main",
      selected_model: "gpt-5",
      event_count: 1,
      message_snapshot_count: 1,
      issue_count: 0,
      degraded: false,
      conversation_preview: "summary",
      search_text: "summary #{session_id}",
      message_count: 1,
      activity_count: 1,
      source_paths: { "source" => "/tmp/#{session_id}.json" },
      source_fingerprint: { "complete" => true },
      summary_payload: summary_payload || { "id" => session_id, "degraded" => false },
      detail_payload: { "id" => session_id, "conversation" => [] },
      indexed_at: Time.zone.parse("2026-04-30T00:00:00Z")
    )
  end

  def parse_time(value)
    value && Time.zone.parse(value)
  end
end

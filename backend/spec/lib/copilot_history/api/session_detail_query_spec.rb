require "rails_helper"

RSpec.describe CopilotHistory::Api::SessionDetailQuery do
  subject(:query) { described_class.new }

  describe "#call" do
    it "returns the stored detail payload for an exact session_id match without reconstructing fields" do
      create_session(
        session_id: "session-12",
        source_format: "legacy",
        detail_payload: {
          "id" => "session-12",
          "source_format" => "legacy",
          "header" => { "title" => "wrong session" },
          "conversation" => []
        }
      )
      detail_payload = {
        "id" => "session-123",
        "source_format" => "current",
        "header" => { "title" => "saved detail" },
        "message_snapshots" => [ { "role" => "user", "content" => "hello" } ],
        "conversation" => [ { "type" => "message", "text" => "hello" } ],
        "activity" => [ { "kind" => "tool_call" } ],
        "timeline" => [ { "kind" => "message" } ],
        "degraded" => false,
        "issues" => []
      }
      create_session(session_id: "session-123", source_format: "current", detail_payload: detail_payload)

      result = query.call(session_id: "session-123")

      expect(result).to eq(
        CopilotHistory::Api::Types::SessionLookupResult::Found.new(detail_payload: detail_payload)
      )
      expect(result.detail_payload).to eq(detail_payload)
      expect(result).not_to respond_to(:status)
    end

    it "returns legacy detail payloads through the same found result contract" do
      detail_payload = {
        "id" => "legacy-session",
        "source_format" => "legacy",
        "header" => { "title" => "legacy detail" },
        "conversation" => [],
        "activity" => [],
        "timeline" => [],
        "degraded" => true,
        "issues" => [ { "code" => "legacy_issue" } ]
      }
      create_session(session_id: "legacy-session", source_format: "legacy", detail_payload: detail_payload)

      expect(query.call(session_id: "legacy-session")).to eq(
        CopilotHistory::Api::Types::SessionLookupResult::Found.new(detail_payload: detail_payload)
      )
    end

    it "returns not_found when the stored read model does not include the requested session id" do
      create_session(session_id: "session-123", source_format: "current")

      expect(query.call(session_id: "missing-session")).to eq(
        CopilotHistory::Api::Types::SessionLookupResult::NotFound.new(session_id: "missing-session")
      )
    end

    it "returns not_found when the read model is empty" do
      expect(query.call(session_id: "missing-session")).to eq(
        CopilotHistory::Api::Types::SessionLookupResult::NotFound.new(session_id: "missing-session")
      )
    end

    it "does not call the raw session catalog reader when detail is requested" do
      detail_payload = { "id" => "session-123", "conversation" => [] }
      create_session(session_id: "session-123", detail_payload: detail_payload)

      expect(CopilotHistory::SessionCatalogReader).not_to receive(:new)

      result = query.call(session_id: "session-123")

      expect(result.detail_payload).to eq(detail_payload)
    end
  end

  def create_session(session_id:, source_format: "current", detail_payload: nil)
    CopilotSession.create!(
      session_id: session_id,
      source_format: source_format,
      source_state: "complete",
      created_at_source: Time.zone.parse("2026-04-26T10:00:00Z"),
      updated_at_source: Time.zone.parse("2026-04-26T10:05:00Z"),
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
      search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION,
      message_count: 1,
      activity_count: 1,
      source_paths: { "source" => "/tmp/#{session_id}.json" },
      source_fingerprint: { "complete" => true },
      summary_payload: { "id" => session_id, "degraded" => false },
      detail_payload: detail_payload || { "id" => session_id, "conversation" => [] },
      indexed_at: Time.zone.parse("2026-04-30T00:00:00Z")
    )
  end
end

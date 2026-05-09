require "rails_helper"

RSpec.describe "API Sessions", type: :request do
  include ActiveSupport::Testing::TimeHelpers

  before do
    host! "localhost"
  end

  describe "GET /api/sessions" do
    it "returns current and legacy stored summary payloads through the existing top-level structure" do
      create_copilot_session(
        session_id: "legacy-session",
        source_format: "legacy",
        updated_at_source: "2026-04-26T09:00:00Z",
        summary_payload: {
          "id" => "legacy-session",
          "source_format" => "legacy",
          "created_at" => "2026-04-26T08:30:00Z",
          "updated_at" => "2026-04-26T09:00:00Z",
          "workspace" => { "cwd" => "/work/legacy-session" },
          "model" => nil,
          "source_state" => "complete",
          "conversation_summary" => "legacy summary",
          "degraded" => false,
          "issues" => []
        }
      )
      create_copilot_session(
        session_id: "current-session",
        source_format: "current",
        updated_at_source: "2026-04-26T10:00:00Z",
        summary_payload: {
          "id" => "current-session",
          "source_format" => "current",
          "created_at" => "2026-04-26T09:30:00Z",
          "updated_at" => "2026-04-26T10:00:00Z",
          "workspace" => { "cwd" => "/work/current-session" },
          "model" => "gpt-5",
          "source_state" => "degraded",
          "conversation_summary" => "current summary",
          "degraded" => true,
          "issues" => [ { "code" => "partial" } ]
        }
      )

      get "/api/sessions", params: { from: "2026-04-01", to: "2026-04-30" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [
          {
            id: "current-session",
            source_format: "current",
            created_at: "2026-04-26T09:30:00Z",
            updated_at: "2026-04-26T10:00:00Z",
            workspace: { cwd: "/work/current-session" },
            model: "gpt-5",
            source_state: "degraded",
            conversation_summary: "current summary",
            degraded: true,
            issues: [ { code: "partial" } ]
          },
          {
            id: "legacy-session",
            source_format: "legacy",
            created_at: "2026-04-26T08:30:00Z",
            updated_at: "2026-04-26T09:00:00Z",
            workspace: { cwd: "/work/legacy-session" },
            model: nil,
            source_state: "complete",
            conversation_summary: "legacy summary",
            degraded: false,
            issues: []
          }
        ],
        meta: {
          count: 2,
          partial_results: true
        }
      )
    end

    it "applies date ranges, display-time ordering, tie-break ordering, and limit at request level" do
      create_copilot_session(session_id: "outside", updated_at_source: "2026-03-31T23:59:59Z")
      create_copilot_session(session_id: "same-b", updated_at_source: "2026-04-26T10:00:00Z")
      create_copilot_session(session_id: "latest", updated_at_source: "2026-04-27T10:00:00Z")
      create_copilot_session(session_id: "same-a", updated_at_source: "2026-04-26T10:00:00Z")
      create_copilot_session(session_id: "unknown-date", no_display_time: true)

      get "/api/sessions", params: { from: "2026-04-01", to: "2026-04-30", limit: "3" }

      expect(response).to have_http_status(:ok)
      parsed = JSON.parse(response.body, symbolize_names: true)
      expect(parsed[:data].map { |payload| payload[:id] }).to eq(%w[latest same-a same-b])
      expect(parsed[:meta]).to eq(count: 3, partial_results: false)
    end

    it "supports one-sided date ranges without mixing default date bounds" do
      create_copilot_session(session_id: "before", updated_at_source: "2026-04-01T00:00:00Z")
      create_copilot_session(session_id: "after", updated_at_source: "2026-05-01T00:00:00Z")

      get "/api/sessions", params: { from: "2026-04-15" }
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[after])

      get "/api/sessions", params: { to: "2026-04-15" }
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[before])
    end

    it "uses the latest 30 days as the default request range" do
      travel_to Time.zone.parse("2026-05-03T12:00:00Z") do
        create_copilot_session(session_id: "inside-default", updated_at_source: "2026-04-20T00:00:00Z")
        create_copilot_session(session_id: "outside-default", updated_at_source: "2026-04-03T11:59:59Z")

        get "/api/sessions"
      end

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[inside-default])
    end

    it "returns an empty success response when the read model has no sessions" do
      get "/api/sessions", params: { from: "2026-04-01", to: "2026-04-30" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [],
        meta: {
          count: 0,
          partial_results: false
        }
      )
    end

    it "returns 400 error envelopes before running the query for invalid list params" do
      [
        [ { from: "not-a-date" }, { field: "from", reason: "invalid_datetime", value: "not-a-date" } ],
        [ { to: "2026-02-30" }, { field: "to", reason: "invalid_datetime", value: "2026-02-30" } ],
        [ { from: "2026-05-01", to: "2026-04-01" }, { field: "range", reason: "from_after_to" } ],
        [ { limit: "0" }, { field: "limit", reason: "positive_integer_required", value: "0" } ]
      ].each do |params, details|
        expect(CopilotHistory::Api::SessionIndexQuery).not_to receive(:new)

        get "/api/sessions", params: params

        expect(response).to have_http_status(:bad_request)
        expect(JSON.parse(response.body, symbolize_names: true)).to eq(
          error: {
            code: "invalid_session_list_query",
            message: "session list query is invalid",
            details:
          }
        )
      end
    end
  end

  describe "GET /api/sessions/:id" do
    it "returns current stored detail payloads without rereading raw files when include_raw is requested" do
      detail_payload = {
        "id" => "current-session",
        "source_format" => "current",
        "header" => {
          "title" => "current detail",
          "cwd" => "/work/current-session"
        },
        "message_snapshots" => [
          {
            "role" => "user",
            "content" => "saved snapshot"
          }
        ],
        "raw_included" => false,
        "conversation" => {
          "entries" => [
            {
              "sequence" => 1,
              "role" => "user",
              "content" => "saved detail"
            }
          ]
        },
        "activity" => [
          {
            "kind" => "tool_call",
            "name" => "apply_patch"
          }
        ],
        "degraded" => true,
        "issues" => [
          {
            "code" => "partial"
          }
        ],
        "timeline" => []
      }
      create_copilot_session(session_id: "current-session", detail_payload: detail_payload)

      expect(CopilotHistory::SessionCatalogReader).not_to receive(:new)

      get "/api/sessions/current-session", params: { include_raw: "true" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: {
          id: "current-session",
          source_format: "current",
          header: {
            title: "current detail",
            cwd: "/work/current-session"
          },
          message_snapshots: [
            {
              role: "user",
              content: "saved snapshot"
            }
          ],
          raw_included: false,
          conversation: {
            entries: [
              {
                sequence: 1,
                role: "user",
                content: "saved detail"
              }
            ]
          },
          activity: [
            {
              kind: "tool_call",
              name: "apply_patch"
            }
          ],
          degraded: true,
          issues: [
            {
              code: "partial"
            }
          ],
          timeline: []
        }
      )
    end

    it "returns legacy stored detail payloads through the same detail contract" do
      detail_payload = {
        "id" => "legacy-session",
        "source_format" => "legacy",
        "header" => { "title" => "legacy detail" },
        "message_snapshots" => [],
        "conversation" => { "entries" => [] },
        "activity" => [],
        "timeline" => [ { "kind" => "session_started" } ],
        "degraded" => false,
        "issues" => []
      }
      create_copilot_session(session_id: "legacy-session", source_format: "legacy", detail_payload: detail_payload)

      get "/api/sessions/legacy-session"

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: {
          id: "legacy-session",
          source_format: "legacy",
          header: { title: "legacy detail" },
          message_snapshots: [],
          conversation: { entries: [] },
          activity: [],
          timeline: [ { kind: "session_started" } ],
          degraded: false,
          issues: []
        }
      )
    end

    it "returns session_not_found with the requested session id for missing read model rows" do
      get "/api/sessions/missing-session"

      expect(response).to have_http_status(:not_found)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        error: {
          code: "session_not_found",
          message: "session was not found",
          details: {
            session_id: "missing-session"
          }
        }
      )
    end

    it "returns session_not_found when the read model is empty" do
      get "/api/sessions/missing-session"

      expect(response).to have_http_status(:not_found)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        error: {
          code: "session_not_found",
          message: "session was not found",
          details: {
            session_id: "missing-session"
          }
        }
      )
    end
  end

  describe "read-only contract" do
    it "does not expose mutating session routes" do
      post "/api/sessions"
      expect(response).to have_http_status(:not_found)

      patch "/api/sessions/current-session"
      expect(response).to have_http_status(:not_found)

      delete "/api/sessions/current-session"
      expect(response).to have_http_status(:not_found)
    end
  end

  def create_copilot_session(session_id:, source_format: "current", created_at_source: nil, updated_at_source: nil, summary_payload: nil, detail_payload: nil, no_display_time: false)
    CopilotSession.create!(
      session_id: session_id,
      source_format: source_format,
      source_state: "complete",
      created_at_source: no_display_time ? nil : parse_time(created_at_source),
      updated_at_source: no_display_time ? nil : parse_time(updated_at_source || created_at_source || "2026-04-26T10:00:00Z"),
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
      summary_payload: summary_payload || { "id" => session_id, "degraded" => false, "issues" => [] },
      detail_payload: detail_payload || { "id" => session_id, "conversation" => {}, "timeline" => [] },
      indexed_at: Time.zone.parse("2026-04-30T00:00:00Z")
    )
  end

  def parse_time(value)
    value && Time.zone.parse(value)
  end
end

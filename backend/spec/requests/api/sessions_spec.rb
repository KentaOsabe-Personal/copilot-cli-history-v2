require "rails_helper"

RSpec.describe "API Sessions", type: :request do
  include ActiveSupport::Testing::TimeHelpers

  before do
    host! "localhost"
  end

  describe "GET /api/sessions" do
    # 概要・目的: 「returns current and legacy stored summary payloads through the existing top-level
    #   structure」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「returns current and legacy stored summary payloads through the existing top-level
    #   structure」の条件・入力・操作を実行する。
    # 期待値: current and legacy stored summary payloads through the existing top-level structure を返すこと。
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

    # 概要・目的: 「applies date ranges, display-time ordering, tie-break ordering, and limit at request
    #   level」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「applies date ranges, display-time ordering, tie-break ordering, and limit at request
    #   level」の条件・入力・操作を実行する。
    # 期待値: date ranges, display-time ordering, tie-break ordering, and limit at request level が適用されること。
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

    # 概要・目的: 「supports one-sided date ranges without mixing default date bounds」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「supports one-sided date ranges without mixing default date bounds」の条件・入力・操作を実行する。
    # 期待値: 「supports one-sided date ranges without mixing default date bounds」で示す状態または振る舞いが成立すること。
    it "supports one-sided date ranges without mixing default date bounds" do
      create_copilot_session(session_id: "before", updated_at_source: "2026-04-01T00:00:00Z")
      create_copilot_session(session_id: "after", updated_at_source: "2026-05-01T00:00:00Z")

      get "/api/sessions", params: { from: "2026-04-15" }
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[after])

      get "/api/sessions", params: { to: "2026-04-15" }
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[before])
    end

    # 概要・目的: 「uses the latest 30 days as the default request range」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「uses the latest 30 days as the default request range」の条件・入力・操作を実行する。
    # 期待値: the latest 30 days as the default request range が使われること。
    it "uses the latest 30 days as the default request range" do
      travel_to Time.zone.parse("2026-05-03T12:00:00Z") do
        create_copilot_session(session_id: "inside-default", updated_at_source: "2026-04-20T00:00:00Z")
        create_copilot_session(session_id: "outside-default", updated_at_source: "2026-04-03T11:59:59Z")

        get "/api/sessions"
      end

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[inside-default])
    end

    # 概要・目的: 「returns an empty success response when the read model has no sessions」を通じて、HTTP
    #   レスポンスとエラー契約を検証する。
    # テストケース: 「returns an empty success response when the read model has no sessions」の条件・入力・操作を実行する。
    # 期待値: an empty success response when the read model has no sessions を返すこと。
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

    # 概要・目的: 「filters sessions by search text while preserving the existing response shape」を通じて、HTTP
    #   レスポンスとエラー契約を検証する。
    # テストケース: 「filters sessions by search text while preserving the existing response shape」の条件・入力・操作を実行する。
    # 期待値: sessions by search text while preserving the existing response shape で絞り込まれること。
    it "filters sessions by search text while preserving the existing response shape" do
      create_copilot_session(
        session_id: "matching",
        updated_at_source: "2026-04-26T10:00:00Z",
        search_text: "tool call apply_patch failed",
        summary_payload: {
          "id" => "matching",
          "degraded" => true,
          "issues" => [ { "code" => "partial" } ]
        }
      )
      create_copilot_session(
        session_id: "missing",
        updated_at_source: "2026-04-27T10:00:00Z",
        search_text: "unrelated history",
        summary_payload: {
          "id" => "missing",
          "degraded" => false,
          "issues" => []
        }
      )

      get "/api/sessions", params: { search: "apply_patch" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [
          {
            id: "matching",
            degraded: true,
            issues: [ { code: "partial" } ]
          }
        ],
        meta: {
          count: 1,
          partial_results: true
        }
      )
    end

    # 概要・目的: 「combines search text with date range and returns an empty success for no matches」を通じて、検索・日付条件と
    #   query 組み立てを検証する。
    # テストケース: 「combines search text with date range and returns an empty success for no
    #   matches」の条件・入力・操作を実行する。
    # 期待値: search text と date range and returns an empty success for no matches が組み合わせて処理されること。
    it "combines search text with date range and returns an empty success for no matches" do
      create_copilot_session(session_id: "outside-date", updated_at_source: "2026-03-31T23:59:59Z", search_text: "gpt-5 tokenizer")
      create_copilot_session(session_id: "inside-date", updated_at_source: "2026-04-20T00:00:00Z", search_text: "gpt-5 tokenizer")
      create_copilot_session(session_id: "inside-missing", updated_at_source: "2026-04-21T00:00:00Z", search_text: "unrelated")

      get "/api/sessions", params: { from: "2026-04-01", to: "2026-04-30", search: "gpt-5" }
      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[inside-date])

      get "/api/sessions", params: { from: "2026-04-01", to: "2026-04-30", search: "absent" }
      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [],
        meta: {
          count: 0,
          partial_results: false
        }
      )
    end

    # 概要・目的: cwd で検索した場合も既存の一覧 API response shape を維持する契約を検証する。
    # テストケース: search_text ではなく cwd だけに一致する session を検索する。
    # 期待値: 保存済み summary、meta、degraded、issue 情報が既存 shape のまま返ること。
    it "filters sessions by cwd while preserving the existing response shape" do
      create_copilot_session(
        session_id: "matching-cwd",
        updated_at_source: "2026-04-26T10:00:00Z",
        cwd: "/Users/example/cwd-search-target",
        search_text: "unrelated history",
        summary_payload: {
          "id" => "matching-cwd",
          "degraded" => true,
          "issues" => [ { "code" => "partial" } ]
        }
      )
      create_copilot_session(
        session_id: "missing-cwd",
        updated_at_source: "2026-04-27T10:00:00Z",
        cwd: "/Users/example/other",
        search_text: "unrelated history",
        summary_payload: {
          "id" => "missing-cwd",
          "degraded" => false,
          "issues" => []
        }
      )

      get "/api/sessions", params: { search: "cwd-search-target" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [
          {
            id: "matching-cwd",
            degraded: true,
            issues: [ { code: "partial" } ]
          }
        ],
        meta: {
          count: 1,
          partial_results: true
        }
      )
    end

    # 概要・目的: cwd に一致しない検索語は失敗ではなく空結果になる契約を検証する。
    # テストケース: cwd と search_text のどちらにも一致しない検索語で一覧 API を呼び出す。
    # 期待値: HTTP 200 と空の一覧 response が返ること。
    it "returns an empty success response when no cwd or search text matches" do
      create_copilot_session(session_id: "missing-cwd", cwd: "/Users/example/other", search_text: "unrelated history")

      get "/api/sessions", params: { search: "cwd-search-target" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        data: [],
        meta: {
          count: 0,
          partial_results: false
        }
      )
    end

    # 概要・目的: 「returns a 400 error envelope for invalid search text before running the query」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns a 400 error envelope for invalid search text before running the query」の条件・入力・操作を実行する。
    # 期待値: a 400 error envelope for invalid search text before running the query を返すこと。
    it "returns a 400 error envelope for invalid search text before running the query" do
      expect(CopilotHistory::Api::SessionIndexQuery).not_to receive(:new)

      get "/api/sessions", params: { search: "hello\u0000world" }

      expect(response).to have_http_status(:bad_request)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        error: {
          code: "invalid_session_list_query",
          message: "session list query is invalid",
          details: {
            field: "search",
            reason: "control_character",
            value: "hello\u0000world"
          }
        }
      )
    end

    # 概要・目的: 「does not read raw files for search requests」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「does not read raw files for search requests」の条件・入力・操作を実行する。
    # 期待値: read raw files for search requests しないこと。
    it "does not read raw files for search requests" do
      create_copilot_session(session_id: "matching", cwd: "/work/saved-read-model", search_text: "unrelated")
      expect(CopilotHistory::SessionCatalogReader).not_to receive(:new)

      get "/api/sessions", params: { search: "saved-read-model" }

      expect(response).to have_http_status(:ok)
      expect(JSON.parse(response.body, symbolize_names: true)[:data].map { |payload| payload[:id] }).to eq(%w[matching])
    end

    # 概要・目的: 「returns 400 error envelopes before running the query for invalid list params」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns 400 error envelopes before running the query for invalid list params」の条件・入力・操作を実行する。
    # 期待値: 400 error envelopes before running the query for invalid list params を返すこと。
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
    # 概要・目的: 「returns current stored detail payloads without rereading raw files when include_raw is
    #   requested」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「returns current stored detail payloads without rereading raw files when include_raw is
    #   requested」の条件・入力・操作を実行する。
    # 期待値: current stored detail payloads without rereading raw files when include_raw is requested を返すこと。
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

    # 概要・目的: 「returns legacy stored detail payloads through the same detail contract」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns legacy stored detail payloads through the same detail contract」の条件・入力・操作を実行する。
    # 期待値: legacy stored detail payloads through the same detail contract を返すこと。
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

    # 概要・目的: 「returns session_not_found with the requested session id for missing read model rows」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns session_not_found with the requested session id for missing read model
    #   rows」の条件・入力・操作を実行する。
    # 期待値: session_not_found with the requested session id for missing read model rows を返すこと。
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

    # 概要・目的: 「returns session_not_found when the read model is empty」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「returns session_not_found when the read model is empty」の条件・入力・操作を実行する。
    # 期待値: session_not_found when the read model is empty を返すこと。
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
    # 概要・目的: 「does not expose mutating session routes」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「does not expose mutating session routes」の条件・入力・操作を実行する。
    # 期待値: expose mutating session routes しないこと。
    it "does not expose mutating session routes" do
      post "/api/sessions"
      expect(response).to have_http_status(:not_found)

      patch "/api/sessions/current-session"
      expect(response).to have_http_status(:not_found)

      delete "/api/sessions/current-session"
      expect(response).to have_http_status(:not_found)
    end
  end

  def create_copilot_session(session_id:, source_format: "current", created_at_source: nil, updated_at_source: nil, summary_payload: nil, detail_payload: nil, no_display_time: false, search_text: nil, cwd: "/work/#{session_id}")
    CopilotSession.create!(
      session_id: session_id,
      source_format: source_format,
      source_state: "complete",
      created_at_source: no_display_time ? nil : parse_time(created_at_source),
      updated_at_source: no_display_time ? nil : parse_time(updated_at_source || created_at_source || "2026-04-26T10:00:00Z"),
      cwd: cwd,
      git_root: "/work/#{session_id}",
      repository: "example/repo",
      branch: "main",
      selected_model: "gpt-5",
      event_count: 1,
      message_snapshot_count: 1,
      issue_count: 0,
      degraded: false,
      conversation_preview: "summary",
      search_text: search_text || "summary #{session_id}",
      search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION,
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

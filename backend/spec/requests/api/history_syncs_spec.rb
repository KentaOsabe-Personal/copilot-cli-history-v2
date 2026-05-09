require "rails_helper"

RSpec.describe "API History Syncs", :copilot_history, type: :request do
  around do |example|
    original_copilot_home = ENV["COPILOT_HOME"]
    original_home = ENV["HOME"]

    example.run
  ensure
    ENV["COPILOT_HOME"] = original_copilot_home
    ENV["HOME"] = original_home
  end

  before do
    host! "localhost"
  end

  describe "POST /api/history/sync" do
    it "syncs mixed current and legacy sessions and returns the terminal run counts" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        post "/api/history/sync"

        expect(response).to have_http_status(:ok)
        payload = JSON.parse(response.body, symbolize_names: true)
        sync_run = HistorySyncRun.order(:id).last

        expect(payload).to eq(
          data: {
            sync_run: {
              id: sync_run.id,
              status: "succeeded",
              started_at: sync_run.started_at.iso8601,
              finished_at: sync_run.finished_at.iso8601
            },
            counts: {
              processed_count: 2,
              inserted_count: 2,
              updated_count: 0,
              saved_count: 2,
              skipped_count: 0,
              failed_count: 0,
              degraded_count: 0
            }
          }
        )
        expect(sync_run).to have_attributes(
          status: "succeeded",
          processed_count: 2,
          inserted_count: 2,
          saved_count: 2,
          running_lock_key: nil
        )
        expect(CopilotSession.pluck(:session_id)).to contain_exactly("current-schema-mixed", "legacy-schema-mixed")
      end
    end

    it "skips unchanged sessions on a repeated sync without rewriting payloads or indexed timestamps" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        post "/api/history/sync"
        current_session = CopilotSession.find_by!(session_id: "current-schema-mixed")
        original_indexed_at = current_session.indexed_at
        original_summary_payload = current_session.summary_payload

        post "/api/history/sync"

        expect(response).to have_http_status(:ok)
        payload = JSON.parse(response.body, symbolize_names: true)
        expect(payload.dig(:data, :counts)).to include(
          processed_count: 2,
          inserted_count: 0,
          updated_count: 0,
          saved_count: 0,
          skipped_count: 2,
          failed_count: 0
        )
        expect(current_session.reload.indexed_at).to eq(original_indexed_at)
        expect(current_session.summary_payload).to eq(original_summary_payload)
      end
    end

    it "updates changed raw files without duplicating the existing read model row" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s
        events_path = root.join("session-state/current-schema-mixed/events.jsonl")

        post "/api/history/sync"
        expect(CopilotSession.count).to eq(2)

        events_path.write(<<~JSONL)
          {"type":"user.message","data":{"content":"current mixed question"},"id":"event-1","timestamp":"2026-04-28T04:00:01Z","parentId":null}
          {"type":"assistant.message","data":{"content":"current mixed answer"},"id":"event-2","timestamp":"2026-04-28T04:00:02Z","parentId":"event-1"}
          {"type":"user.message","data":{"content":"updated raw file content"},"id":"event-3","timestamp":"2026-04-28T04:00:03Z","parentId":"event-2"}
        JSONL

        post "/api/history/sync"

        expect(response).to have_http_status(:ok)
        payload = JSON.parse(response.body, symbolize_names: true)
        expect(payload.dig(:data, :counts)).to include(
          processed_count: 2,
          inserted_count: 0,
          updated_count: 1,
          saved_count: 1,
          skipped_count: 1
        )
        expect(CopilotSession.where(session_id: "current-schema-mixed").count).to eq(1)
        expect(CopilotSession.count).to eq(2)
        expect(CopilotSession.find_by!(session_id: "current-schema-mixed")).to have_attributes(
          event_count: 3,
          message_count: 3
        )
      end
    end

    it "returns a root failure as a 503 error envelope and does not overwrite existing sessions" do
      existing_session = CopilotSession.create!(
        session_id: "existing-session",
        source_format: "current",
        source_state: "complete",
        event_count: 0,
        message_snapshot_count: 0,
        issue_count: 0,
        degraded: false,
        search_text: "existing session",
        message_count: 0,
        activity_count: 0,
        source_paths: { "events" => "/tmp/existing/events.jsonl" },
        source_fingerprint: { "complete" => true, "artifacts" => {} },
        summary_payload: { "id" => "existing-session" },
        detail_payload: { "id" => "existing-session" },
        indexed_at: Time.zone.parse("2026-04-29 09:00:00")
      )

      Dir.mktmpdir("copilot-history-home") do |home|
        ENV.delete("COPILOT_HOME")
        ENV["HOME"] = home

        post "/api/history/sync"

        expect(response).to have_http_status(:service_unavailable)
        payload = JSON.parse(response.body, symbolize_names: true)
        sync_run = HistorySyncRun.order(:id).last
        expect(payload).to eq(
          error: {
            code: "root_missing",
            message: "history root does not exist",
            details: {
              path: File.join(home, ".copilot")
            }
          },
          meta: {
            sync_run: {
              id: sync_run.id,
              status: "failed",
              started_at: sync_run.started_at.iso8601,
              finished_at: sync_run.finished_at.iso8601
            },
            counts: {
              processed_count: 0,
              inserted_count: 0,
              updated_count: 0,
              saved_count: 0,
              skipped_count: 0,
              failed_count: 1,
              degraded_count: 0
            }
          }
        )
        expect(existing_session.reload.summary_payload).to eq("id" => "existing-session")
      end
    end

    it "returns degraded sessions as completed_with_issues with saved issue information" do
      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        workspace_path = root.join("session-state/current-schema-mixed/workspace.yaml")
        ENV["COPILOT_HOME"] = root.to_s

        with_permission_denied(workspace_path) do
          post "/api/history/sync"
        end

        expect(response).to have_http_status(:ok)
        payload = JSON.parse(response.body, symbolize_names: true)
        expect(payload.dig(:data, :sync_run, :status)).to eq("completed_with_issues")
        expect(payload.dig(:data, :counts)).to include(
          processed_count: 2,
          inserted_count: 2,
          saved_count: 2,
          degraded_count: 1,
          failed_count: 0
        )
        degraded_session = CopilotSession.find_by!(session_id: "current-schema-mixed")
        expect(degraded_session).to have_attributes(
          source_state: "degraded",
          degraded: true,
          issue_count: 1
        )
        expect(degraded_session.summary_payload.fetch("issues").first).to include(
          "code" => "current.workspace_unreadable",
          "source_path" => workspace_path.to_s
        )
      end
    end

    it "returns conflict without overwriting an existing running sync run" do
      running_run = HistorySyncRun.create!(
        status: "running",
        started_at: Time.zone.parse("2026-04-30 08:55:00"),
        running_lock_key: CopilotHistory::Sync::HistorySyncService::RUNNING_LOCK_KEY
      )

      with_copilot_history_fixture("current_schema_mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        post "/api/history/sync"
      end

      expect(response).to have_http_status(:conflict)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        error: {
          code: "history_sync_running",
          message: "history sync is already running",
          details: {
            sync_run_id: running_run.id,
            started_at: "2026-04-30T08:55:00Z"
          }
        }
      )
      expect(running_run.reload).to have_attributes(
        status: "running",
        processed_count: 0,
        running_lock_key: CopilotHistory::Sync::HistorySyncService::RUNNING_LOCK_KEY
      )
    end

    it "returns persistence failures from the service as a 500 error envelope" do
      failed_run = HistorySyncRun.create!(
        status: "failed",
        started_at: Time.zone.parse("2026-04-30 08:55:00"),
        finished_at: Time.zone.parse("2026-04-30 08:55:01"),
        failed_count: 1,
        failure_summary: "ActiveRecord::RecordInvalid: Validation failed"
      )
      failed_result = CopilotHistory::Sync::SyncResult::Failed.new(
        sync_run: failed_run,
        code: "history_sync_failed",
        message: "history sync failed",
        details: { failure_class: "ActiveRecord::RecordInvalid" }
      )
      service = instance_double(CopilotHistory::Sync::HistorySyncService, call: failed_result)
      allow(CopilotHistory::Sync::HistorySyncService).to receive(:new).and_return(service)

      post "/api/history/sync"

      expect(response).to have_http_status(:internal_server_error)
      expect(JSON.parse(response.body, symbolize_names: true)).to eq(
        error: {
          code: "history_sync_failed",
          message: "history sync failed",
          details: {
            failure_class: "ActiveRecord::RecordInvalid",
            sync_run_id: failed_run.id
          }
        },
        meta: {
          sync_run: {
            id: failed_run.id,
            status: "failed",
            started_at: "2026-04-30T08:55:00Z",
            finished_at: "2026-04-30T08:55:01Z"
          },
          counts: {
            processed_count: 0,
            inserted_count: 0,
            updated_count: 0,
            saved_count: 0,
            skipped_count: 0,
            failed_count: 1,
            degraded_count: 0
          }
        }
      )
    end
  end
end

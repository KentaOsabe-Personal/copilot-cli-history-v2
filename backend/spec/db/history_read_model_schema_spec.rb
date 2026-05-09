require "rails_helper"

RSpec.describe "history read model schema" do
  describe "copilot_sessions" do
    subject(:columns) { ActiveRecord::Base.connection.columns(:copilot_sessions).index_by(&:name) }

    it "stores one read model row per session with source dates, payloads, metadata, and indexes" do
      expect(columns.keys).to include(
        "session_id",
        "source_format",
        "source_state",
        "created_at_source",
        "updated_at_source",
        "cwd",
        "git_root",
        "repository",
        "branch",
        "selected_model",
        "event_count",
        "message_snapshot_count",
        "issue_count",
        "degraded",
        "conversation_preview",
        "search_text",
        "message_count",
        "activity_count",
        "source_paths",
        "source_fingerprint",
        "summary_payload",
        "detail_payload",
        "indexed_at"
      )

      expect(columns["session_id"].null).to be(false)
      expect(columns["created_at_source"].null).to be(true)
      expect(columns["updated_at_source"].null).to be(true)
      expect(columns["summary_payload"].type).to eq(:json)
      expect(columns["detail_payload"].type).to eq(:json)
      expect(columns["source_paths"].type).to eq(:json)
      expect(columns["source_fingerprint"].type).to eq(:json)
      expect(columns["event_count"].default).to eq(0)
      expect(columns["message_snapshot_count"].default).to eq(0)
      expect(columns["issue_count"].default).to eq(0)
      expect(columns["degraded"].default).to eq(false)
      expect(columns["search_text"].null).to be(false)
      expect(columns["message_count"].default).to eq(0)
      expect(columns["activity_count"].default).to eq(0)
    end

    it "defines uniqueness and query-supporting indexes" do
      indexes = ActiveRecord::Base.connection.indexes(:copilot_sessions)

      expect(indexes).to include(
        have_attributes(columns: [ "session_id" ], unique: true),
        have_attributes(columns: [ "updated_at_source" ]),
        have_attributes(columns: [ "created_at_source" ]),
        have_attributes(columns: [ "source_format" ]),
        have_attributes(columns: [ "source_state" ]),
        have_attributes(columns: [ "repository" ]),
        have_attributes(columns: [ "branch" ])
      )
    end
  end

  describe "history_sync_runs" do
    subject(:columns) { ActiveRecord::Base.connection.columns(:history_sync_runs).index_by(&:name) }

    it "stores sync run outcomes independently of session rows" do
      expect(columns.keys).to include(
        "started_at",
        "finished_at",
        "status",
        "processed_count",
        "inserted_count",
        "updated_count",
        "saved_count",
        "skipped_count",
        "failed_count",
        "degraded_count",
        "running_lock_key",
        "failure_summary",
        "degradation_summary"
      )

      expect(columns["started_at"].null).to be(false)
      expect(columns["finished_at"].null).to be(true)
      expect(columns["status"].null).to be(false)
      expect(columns["processed_count"].default).to eq(0)
      expect(columns["inserted_count"].default).to eq(0)
      expect(columns["updated_count"].default).to eq(0)
      expect(columns["saved_count"].default).to eq(0)
      expect(columns["skipped_count"].default).to eq(0)
      expect(columns["failed_count"].default).to eq(0)
      expect(columns["degraded_count"].default).to eq(0)
      expect(columns["running_lock_key"].null).to be(true)
    end

    it "defines status, started_at, and running lock indexes" do
      indexes = ActiveRecord::Base.connection.indexes(:history_sync_runs)

      expect(indexes).to include(
        have_attributes(columns: [ "status" ]),
        have_attributes(columns: [ "started_at" ]),
        have_attributes(columns: [ "running_lock_key" ], unique: true)
      )
    end
  end
end

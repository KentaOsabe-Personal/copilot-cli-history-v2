require "rails_helper"

RSpec.describe "history read model persistence" do
  around do |example|
    Dir.mktmpdir("history-read-model-persistence") do |dir|
      @tmpdir = Pathname.new(dir)
      example.run
    end
  end

  describe "copilot_sessions" do
    # 概要・目的: 「persists current and legacy builder attributes in the same table for payload and metadata
    #   reuse」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「persists current and legacy builder attributes in the same table for payload and metadata
    #   reuse」の条件・入力・操作を実行する。
    # 期待値: current and legacy builder attributes in the same table for payload and metadata reuse が永続化されること。
    it "persists current and legacy builder attributes in the same table for payload and metadata reuse" do
      current_source = write_source("current/events.jsonl", "{}\n")
      legacy_source = write_source("legacy/session.json", "{}")
      current_attributes = build_attributes(
        session_id: "current-persisted",
        source_format: :current,
        updated_at: "2026-04-28T01:01:00Z",
        source_paths: { events: current_source },
        content: "current answer"
      )
      legacy_attributes = build_attributes(
        session_id: "legacy-persisted",
        source_format: :legacy,
        created_at: nil,
        updated_at: nil,
        source_paths: { source: legacy_source },
        content: "legacy answer"
      )

      CopilotSession.create!(current_attributes)
      CopilotSession.create!(legacy_attributes)

      current = CopilotSession.find_by!(session_id: "current-persisted")
      legacy = CopilotSession.find_by!(session_id: "legacy-persisted")

      expect(current.source_format).to eq("current")
      expect(current.detail_payload.fetch("conversation")).to include("message_count" => 1)
      expect(current.source_paths).to eq("events" => current_source.to_s)
      expect(current.source_fingerprint.dig("artifacts", "events")).to include(
        "path" => current_source.to_s,
        "status" => "ok"
      )
      expect(legacy.source_format).to eq("legacy")
      expect(legacy.summary_payload).to include(
        "id" => "legacy-persisted",
        "source_format" => "legacy",
        "created_at" => nil,
        "updated_at" => nil
      )
      expect(legacy.created_at_source).to be_nil
      expect(legacy.updated_at_source).to be_nil
    end

    # 概要・目的: 「updates a regenerated session by natural key without creating a duplicate row」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「updates a regenerated session by natural key without creating a duplicate row」の条件・入力・操作を実行する。
    # 期待値: a regenerated session by natural key without creating a duplicate row が更新されること。
    it "updates a regenerated session by natural key without creating a duplicate row" do
      source = write_source("current/events.jsonl", "{}\n")
      original_attributes = build_attributes(
        session_id: "regenerated-session",
        source_format: :current,
        updated_at: "2026-04-28T01:00:00Z",
        source_paths: { events: source },
        content: "first"
      )
      regenerated_attributes = build_attributes(
        session_id: "regenerated-session",
        source_format: :current,
        updated_at: "2026-04-28T01:05:00Z",
        source_paths: { events: source },
        content: "updated"
      )
      record = CopilotSession.create!(original_attributes)

      record.update!(regenerated_attributes.except(:session_id))
      reloaded = CopilotSession.find_by!(session_id: "regenerated-session")

      expect(CopilotSession.where(session_id: "regenerated-session").count).to eq(1)
      expect(reloaded.conversation_preview).to eq("updated")
      expect(reloaded.updated_at_source).to eq(Time.iso8601("2026-04-28T01:05:00Z"))
      expect(reloaded.summary_payload.dig("conversation_summary", "preview")).to eq("updated")
    end
  end

  describe "history_sync_runs" do
    # 概要・目的: 「persists root failures without requiring any session rows」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「persists root failures without requiring any session rows」の条件・入力・操作を実行する。
    # 期待値: root failures without requiring any session rows が永続化されること。
    it "persists root failures without requiring any session rows" do
      run = HistorySyncRun.create!(
        started_at: Time.zone.parse("2026-04-30 03:00:00"),
        finished_at: Time.zone.parse("2026-04-30 03:00:02"),
        status: "failed",
        processed_count: 0,
        inserted_count: 0,
        updated_count: 0,
        saved_count: 0,
        skipped_count: 0,
        failed_count: 1,
        degraded_count: 0,
        failure_summary: "history root is unreadable"
      )

      expect(CopilotSession.count).to eq(0)
      expect(HistorySyncRun.find(run.id)).to have_attributes(
        status: "failed",
        failure_summary: "history root is unreadable",
        failed_count: 1
      )
    end

    # 概要・目的: 「persists complete success and degraded completion as distinct operational outcomes」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「persists complete success and degraded completion as distinct operational
    #   outcomes」の条件・入力・操作を実行する。
    # 期待値: complete success and degraded completion as distinct operational outcomes が永続化されること。
    it "persists complete success and degraded completion as distinct operational outcomes" do
      succeeded = HistorySyncRun.create!(
        started_at: Time.zone.parse("2026-04-30 03:00:00"),
        finished_at: Time.zone.parse("2026-04-30 03:00:03"),
        status: "succeeded",
        processed_count: 2,
        inserted_count: 1,
        updated_count: 1,
        saved_count: 2
      )
      completed_with_issues = HistorySyncRun.create!(
        started_at: Time.zone.parse("2026-04-30 03:05:00"),
        finished_at: Time.zone.parse("2026-04-30 03:05:03"),
        status: "completed_with_issues",
        processed_count: 2,
        inserted_count: 2,
        updated_count: 0,
        saved_count: 2,
        degraded_count: 1,
        degradation_summary: "1 session degraded"
      )

      expect(HistorySyncRun.where(status: "succeeded")).to contain_exactly(succeeded)
      expect(HistorySyncRun.where(status: "completed_with_issues")).to contain_exactly(completed_with_issues)
      expect(completed_with_issues.degradation_summary).to eq("1 session degraded")
    end

    # 概要・目的: 「allows multiple terminal rows while enforcing one active running lock」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「allows multiple terminal rows while enforcing one active running lock」の条件・入力・操作を実行する。
    # 期待値: multiple terminal rows while enforcing one active running lock が許可されること。
    it "allows multiple terminal rows while enforcing one active running lock" do
      started_at = Time.zone.parse("2026-04-30 03:00:00")

      HistorySyncRun.create!(
        started_at: started_at,
        finished_at: started_at + 1.second,
        status: "succeeded"
      )
      HistorySyncRun.create!(
        started_at: started_at + 2.seconds,
        finished_at: started_at + 3.seconds,
        status: "failed",
        failed_count: 1
      )
      HistorySyncRun.create!(
        started_at: started_at + 4.seconds,
        status: "running",
        running_lock_key: "history-sync"
      )

      expect {
        HistorySyncRun.create!(
          started_at: started_at + 5.seconds,
          status: "running",
          running_lock_key: "history-sync"
        )
      }.to raise_error(ActiveRecord::RecordNotUnique)
    end
  end

  def write_source(relative_path, content)
    path = @tmpdir.join(relative_path)
    path.dirname.mkpath
    path.write(content)
    path
  end

  def build_attributes(session_id:, source_format:, source_paths:, content:, created_at: "2026-04-28T01:00:00Z", updated_at: nil)
    session = CopilotHistory::Types::NormalizedSession.new(
      session_id:,
      source_format:,
      source_state: :complete,
      created_at:,
      updated_at:,
      events: [
        CopilotHistory::Types::NormalizedEvent.new(
          sequence: 1,
          kind: :message,
          raw_type: "#{source_format}.message",
          occurred_at: updated_at || created_at,
          role: "assistant",
          content:,
          raw_payload: {}
        )
      ],
      message_snapshots: [],
      issues: [],
      source_paths:
    )

    CopilotHistory::Persistence::SessionRecordBuilder.new.call(
      session:,
      indexed_at: Time.zone.parse("2026-04-30 12:00:00")
    )
  end
end

require "rails_helper"

RSpec.describe CopilotHistory::Sync::SyncResult do
  let(:sync_run) do
    HistorySyncRun.new(
      id: 101,
      status: "succeeded",
      started_at: Time.zone.parse("2026-04-30 06:00:00"),
      finished_at: Time.zone.parse("2026-04-30 06:00:02")
    )
  end

  describe CopilotHistory::Sync::SyncResult::Succeeded do
    # 概要・目的: 「carries a terminal sync run and exposes its result kind」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「carries a terminal sync run and exposes its result kind」の条件・入力・操作を実行する。
    # 期待値: a terminal sync run and exposes its result kind が保持されて渡されること。
    it "carries a terminal sync run and exposes its result kind" do
      result = described_class.new(sync_run:)

      expect(result.sync_run).to eq(sync_run)
      expect(result).to be_succeeded
      expect(result).not_to be_conflict
      expect(result).not_to be_failed
    end
  end

  describe CopilotHistory::Sync::SyncResult::Conflict do
    # 概要・目的: 「carries the existing running sync run without replacing it」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「carries the existing running sync run without replacing it」の条件・入力・操作を実行する。
    # 期待値: the existing running sync run without replacing it が保持されて渡されること。
    it "carries the existing running sync run without replacing it" do
      running_run = HistorySyncRun.new(
        id: 102,
        status: "running",
        started_at: Time.zone.parse("2026-04-30 06:01:00"),
        running_lock_key: "history_sync"
      )
      result = described_class.new(running_run:)

      expect(result.running_run).to eq(running_run)
      expect(result).to be_conflict
      expect(result).not_to be_succeeded
      expect(result).not_to be_failed
    end
  end

  describe CopilotHistory::Sync::SyncResult::Failed do
    # 概要・目的: 「carries terminal run, failure code, message, and details for root
    #   failures」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「carries terminal run, failure code, message, and details for root failures」の条件・入力・操作を実行する。
    # 期待値: terminal run, failure code, message, and details for root failures が保持されて渡されること。
    it "carries terminal run, failure code, message, and details for root failures" do
      failed_run = HistorySyncRun.new(
        id: 103,
        status: "failed",
        started_at: Time.zone.parse("2026-04-30 06:02:00"),
        finished_at: Time.zone.parse("2026-04-30 06:02:01")
      )
      result = described_class.new(
        sync_run: failed_run,
        code: "root_missing",
        message: "history root does not exist",
        details: { path: "/tmp/missing-root" }
      )

      expect(result.sync_run).to eq(failed_run)
      expect(result.code).to eq("root_missing")
      expect(result.message).to eq("history root does not exist")
      expect(result.details).to eq(path: "/tmp/missing-root")
      expect(result).to be_failed
      expect(result).not_to be_succeeded
      expect(result).not_to be_conflict
    end
  end
end

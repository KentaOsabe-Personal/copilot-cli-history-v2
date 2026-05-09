require "rails_helper"

RSpec.describe CopilotHistory::Api::Presenters::HistorySyncPresenter do
  subject(:presenter) { described_class.new }

  describe "#call" do
    # 概要・目的: 「presents successful sync runs as an ok data payload with sync run and
    #   counts」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「presents successful sync runs as an ok data payload with sync run and counts」の条件・入力・操作を実行する。
    # 期待値: 「presents successful sync runs as an ok data payload with sync run and counts」で示す状態または振る舞いが成立すること。
    it "presents successful sync runs as an ok data payload with sync run and counts" do
      sync_run = build_sync_run(
        id: 201,
        status: "succeeded",
        processed_count: 3,
        inserted_count: 1,
        updated_count: 1,
        saved_count: 2,
        skipped_count: 1,
        failed_count: 0,
        degraded_count: 0
      )
      result = CopilotHistory::Sync::SyncResult::Succeeded.new(sync_run:)

      status, payload = presenter.call(result:)

      expect(status).to eq(:ok)
      expect(payload).to eq(
        data: {
          sync_run: {
            id: 201,
            status: "succeeded",
            started_at: "2026-04-30T06:00:00Z",
            finished_at: "2026-04-30T06:00:02Z"
          },
          counts: {
            processed_count: 3,
            inserted_count: 1,
            updated_count: 1,
            saved_count: 2,
            skipped_count: 1,
            failed_count: 0,
            degraded_count: 0
          }
        }
      )
    end

    # 概要・目的: 「presents completed_with_issues as a successful payload instead of an error envelope」を通じて、HTTP
    #   レスポンスとエラー契約を検証する。
    # テストケース: 「presents completed_with_issues as a successful payload instead of an error
    #   envelope」の条件・入力・操作を実行する。
    # 期待値: 「presents completed_with_issues as a successful payload instead of an error
    #   envelope」で示す状態または振る舞いが成立すること。
    it "presents completed_with_issues as a successful payload instead of an error envelope" do
      sync_run = build_sync_run(
        id: 202,
        status: "completed_with_issues",
        processed_count: 2,
        inserted_count: 2,
        saved_count: 2,
        degraded_count: 1
      )
      result = CopilotHistory::Sync::SyncResult::Succeeded.new(sync_run:)

      status, payload = presenter.call(result:)

      expect(status).to eq(:ok)
      expect(payload.fetch(:data).fetch(:sync_run).fetch(:status)).to eq("completed_with_issues")
      expect(payload.fetch(:data).fetch(:counts).fetch(:degraded_count)).to eq(1)
    end

    # 概要・目的: 「presents running conflicts as the shared error envelope with existing run
    #   details」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「presents running conflicts as the shared error envelope with existing run
    #   details」の条件・入力・操作を実行する。
    # 期待値: 「presents running conflicts as the shared error envelope with existing run
    #   details」で示す状態または振る舞いが成立すること。
    it "presents running conflicts as the shared error envelope with existing run details" do
      running_run = HistorySyncRun.new(
        id: 203,
        status: "running",
        started_at: Time.zone.parse("2026-04-30 06:03:00"),
        running_lock_key: "history_sync"
      )
      result = CopilotHistory::Sync::SyncResult::Conflict.new(running_run:)

      status, payload = presenter.call(result:)

      expect(status).to eq(:conflict)
      expect(payload).to eq(
        error: {
          code: "history_sync_running",
          message: "history sync is already running",
          details: {
            sync_run_id: 203,
            started_at: "2026-04-30T06:03:00Z"
          }
        }
      )
    end

    # 概要・目的: 「presents root failures with the upstream failure code and path as service
    #   unavailable」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「presents root failures with the upstream failure code and path as service
    #   unavailable」の条件・入力・操作を実行する。
    # 期待値: 「presents root failures with the upstream failure code and path as service
    #   unavailable」で示す状態または振る舞いが成立すること。
    it "presents root failures with the upstream failure code and path as service unavailable" do
      failed_run = build_sync_run(id: 204, status: "failed", failed_count: 1)
      result = CopilotHistory::Sync::SyncResult::Failed.new(
        sync_run: failed_run,
        code: "root_missing",
        message: "history root does not exist",
        details: { path: "/tmp/missing-root" }
      )

      status, payload = presenter.call(result:)

      expect(status).to eq(:service_unavailable)
      expect(payload).to eq(
        error: {
          code: "root_missing",
          message: "history root does not exist",
          details: {
            path: "/tmp/missing-root"
          }
        },
        meta: {
          sync_run: {
            id: 204,
            status: "failed",
            started_at: "2026-04-30T06:00:00Z",
            finished_at: "2026-04-30T06:00:02Z"
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

    # 概要・目的: 「presents persistence failures as internal server errors with failure class details」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「presents persistence failures as internal server errors with failure class
    #   details」の条件・入力・操作を実行する。
    # 期待値: 「presents persistence failures as internal server errors with failure class
    #   details」で示す状態または振る舞いが成立すること。
    it "presents persistence failures as internal server errors with failure class details" do
      failed_run = build_sync_run(id: 205, status: "failed", failed_count: 1)
      result = CopilotHistory::Sync::SyncResult::Failed.new(
        sync_run: failed_run,
        code: "history_sync_failed",
        message: "history sync failed",
        details: { failure_class: "ActiveRecord::RecordInvalid" }
      )

      status, payload = presenter.call(result:)

      expect(status).to eq(:internal_server_error)
      expect(payload.fetch(:error)).to eq(
        code: "history_sync_failed",
        message: "history sync failed",
        details: {
          sync_run_id: 205,
          failure_class: "ActiveRecord::RecordInvalid"
        }
      )
      expect(payload.fetch(:meta).fetch(:sync_run).fetch(:id)).to eq(205)
    end
  end

  def build_sync_run(id:, status:, **counts)
    defaults = {
      processed_count: 0,
      inserted_count: 0,
      updated_count: 0,
      saved_count: 0,
      skipped_count: 0,
      failed_count: 0,
      degraded_count: 0
    }

    HistorySyncRun.new(
      id:,
      status:,
      started_at: Time.zone.parse("2026-04-30 06:00:00"),
      finished_at: Time.zone.parse("2026-04-30 06:00:02"),
      **defaults.merge(counts)
    )
  end
end

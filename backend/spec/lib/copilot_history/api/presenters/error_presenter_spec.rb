require "rails_helper"

RSpec.describe CopilotHistory::Api::Presenters::ErrorPresenter do
  describe "#from_read_failure" do
    # 概要・目的: 「maps each root failure to a 503 envelope while preserving the upstream
    #   code」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「maps each root failure to a 503 envelope while preserving the upstream code」の条件・入力・操作を実行する。
    # 期待値: each root failure が a 503 envelope while preserving the upstream code に変換されること。
    it "maps each root failure to a 503 envelope while preserving the upstream code" do
      [
        CopilotHistory::Errors::ReadErrorCode::ROOT_MISSING,
        CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
        CopilotHistory::Errors::ReadErrorCode::ROOT_UNREADABLE
      ].each do |code|
        failure = CopilotHistory::Types::ReadFailure.new(
          code:,
          path: "/tmp/copilot",
          message: "history root is unavailable"
        )

        status, payload = described_class.new.from_read_failure(failure:)

        expect(status).to eq(:service_unavailable)
        expect(payload).to eq(
          error: {
            code:,
            message: "history root is unavailable",
            details: {
              path: "/tmp/copilot"
            }
          }
        )
      end
    end
  end

  describe "#from_not_found" do
    # 概要・目的: 「maps lookup misses to a 404 session_not_found envelope」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「maps lookup misses to a 404 session_not_found envelope」の条件・入力・操作を実行する。
    # 期待値: lookup misses が a 404 session_not_found envelope に変換されること。
    it "maps lookup misses to a 404 session_not_found envelope" do
      status, payload = described_class.new.from_not_found(session_id: "session-123")

      expect(status).to eq(:not_found)
      expect(payload).to eq(
        error: {
          code: "session_not_found",
          message: "session was not found",
          details: {
            session_id: "session-123"
          }
        }
      )
    end
  end

  describe "#from_invalid_session_list_query" do
    # 概要・目的: 「maps invalid list query results to a 400 invalid_session_list_query envelope」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「maps invalid list query results to a 400 invalid_session_list_query envelope」の条件・入力・操作を実行する。
    # 期待値: invalid list query results が a 400 invalid_session_list_query envelope に変換されること。
    it "maps invalid list query results to a 400 invalid_session_list_query envelope" do
      invalid_result = CopilotHistory::Api::Types::SessionIndexResult::Invalid.new(
        code: "invalid_session_list_query",
        message: "session list query is invalid",
        details: {
          field: "from",
          reason: "invalid_datetime"
        }
      )

      status, payload = described_class.new.from_invalid_session_list_query(invalid_result:)

      expect(status).to eq(:bad_request)
      expect(payload).to eq(
        error: {
          code: "invalid_session_list_query",
          message: "session list query is invalid",
          details: {
            field: "from",
            reason: "invalid_datetime"
          }
        }
      )
    end
  end
end

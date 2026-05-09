require "rails_helper"

RSpec.describe CopilotHistory::Types::ReadResult do
  describe CopilotHistory::Types::ResolvedHistoryRoot do
    # 概要・目的: 「normalizes root paths into Pathname values」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「normalizes root paths into Pathname values」の条件・入力・操作を実行する。
    # 期待値: root paths into Pathname values が正規化されること。
    it "normalizes root paths into Pathname values" do
      root = described_class.new(
        root_path: "/tmp/copilot",
        current_root: "/tmp/copilot/session-state",
        legacy_root: "/tmp/copilot/history-session-state"
      )

      expect(root.root_path).to eq(Pathname("/tmp/copilot"))
      expect(root.current_root).to eq(Pathname("/tmp/copilot/session-state"))
      expect(root.legacy_root).to eq(Pathname("/tmp/copilot/history-session-state"))
    end
  end

  describe CopilotHistory::Types::SessionSource do
    # 概要・目的: 「captures common source descriptor fields for readers」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「captures common source descriptor fields for readers」の条件・入力・操作を実行する。
    # 期待値: common source descriptor fields for readers が保持されること。
    it "captures common source descriptor fields for readers" do
      source = described_class.new(
        format: :current,
        session_id: "session-123",
        source_path: "/tmp/copilot/session-state/session-123",
        artifact_paths: {
          workspace: "/tmp/copilot/session-state/session-123/workspace.yaml",
          events: "/tmp/copilot/session-state/session-123/events.jsonl"
        }
      )

      expect(source.format).to eq(:current)
      expect(source.session_id).to eq("session-123")
      expect(source.source_path).to eq(Pathname("/tmp/copilot/session-state/session-123"))
      expect(source.artifact_paths).to eq(
        workspace: Pathname("/tmp/copilot/session-state/session-123/workspace.yaml"),
        events: Pathname("/tmp/copilot/session-state/session-123/events.jsonl")
      )
    end
  end

  describe CopilotHistory::Types::ReadFailure do
    # 概要・目的: 「captures fatal root failures with stable payload fields」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「captures fatal root failures with stable payload fields」の条件・入力・操作を実行する。
    # 期待値: fatal root failures with stable payload fields が保持されること。
    it "captures fatal root failures with stable payload fields" do
      failure = described_class.new(
        code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
        path: "/tmp/copilot",
        message: "permission denied"
      )

      expect(failure.code).to eq("root_permission_denied")
      expect(failure.path).to eq(Pathname("/tmp/copilot"))
      expect(failure.message).to eq("permission denied")
    end

    # 概要・目的: 「rejects non-root failure codes」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「rejects non-root failure codes」の条件・入力・操作を実行する。
    # 期待値: non-root failure codes が拒否されること。
    it "rejects non-root failure codes" do
      expect do
        described_class.new(
          code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
          path: "/tmp/copilot",
          message: "not fatal"
        )
      end.to raise_error(ArgumentError, /root failure code/i)
    end
  end

  describe CopilotHistory::Types::ReadIssue do
    # 概要・目的: 「captures session-level issues without promoting them to fatal failures」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「captures session-level issues without promoting them to fatal failures」の条件・入力・操作を実行する。
    # 期待値: session-level issues without promoting them to fatal failures が保持されること。
    it "captures session-level issues without promoting them to fatal failures" do
      issue = described_class.new(
        code: CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
        message: "line 3 is invalid json",
        source_path: "/tmp/copilot/events.jsonl",
        sequence: 3,
        severity: :error
      )

      expect(issue.code).to eq("current.event_parse_failed")
      expect(issue.message).to eq("line 3 is invalid json")
      expect(issue.source_path).to eq(Pathname("/tmp/copilot/events.jsonl"))
      expect(issue.sequence).to eq(3)
      expect(issue.severity).to eq(:error)
    end
  end

  describe CopilotHistory::Types::ReadResult::Success do
    # 概要・目的: 「wraps resolved root and sessions in the public success envelope」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「wraps resolved root and sessions in the public success envelope」の条件・入力・操作を実行する。
    # 期待値: resolved root and sessions in the public success envelope が公開用 envelope に包まれること。
    it "wraps resolved root and sessions in the public success envelope" do
      root = CopilotHistory::Types::ResolvedHistoryRoot.new(
        root_path: "/tmp/copilot",
        current_root: "/tmp/copilot/session-state",
        legacy_root: "/tmp/copilot/history-session-state"
      )

      result = described_class.new(root:, sessions: [])

      expect(result.root).to eq(root)
      expect(result.sessions).to eq([])
      expect(result).to be_success
      expect(result).not_to be_failure
    end
  end

  describe CopilotHistory::Types::ReadResult::Failure do
    # 概要・目的: 「wraps fatal root failures in the public failure envelope」を通じて、同期処理の状態管理と副作用を検証する。
    # テストケース: 「wraps fatal root failures in the public failure envelope」の条件・入力・操作を実行する。
    # 期待値: fatal root failures in the public failure envelope が公開用 envelope に包まれること。
    it "wraps fatal root failures in the public failure envelope" do
      failure = CopilotHistory::Types::ReadFailure.new(
        code: CopilotHistory::Errors::ReadErrorCode::ROOT_MISSING,
        path: "/tmp/copilot",
        message: "history root not found"
      )

      result = described_class.new(failure:)

      expect(result.failure).to eq(failure)
      expect(result).to be_failure
      expect(result).not_to be_success
    end
  end
end

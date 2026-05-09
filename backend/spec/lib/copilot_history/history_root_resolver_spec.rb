require "rails_helper"

RSpec.describe CopilotHistory::HistoryRootResolver, :copilot_history do
  around do |example|
    original_copilot_home = ENV["COPILOT_HOME"]
    original_home = ENV["HOME"]

    example.run
  ensure
    ENV["COPILOT_HOME"] = original_copilot_home
    ENV["HOME"] = original_home
  end

  describe "#call" do
    # 概要・目的: 「prefers COPILOT_HOME when it is set」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「prefers COPILOT_HOME when it is set」の条件・入力・操作を実行する。
    # 期待値: 「prefers COPILOT_HOME when it is set」で示す状態または振る舞いが成立すること。
    it "prefers COPILOT_HOME when it is set" do
      with_copilot_history_fixture("mixed_root") do |root|
        ENV["COPILOT_HOME"] = root.to_s
        ENV["HOME"] = Dir.mktmpdir("copilot-history-home")

        resolved = described_class.new.call

        expect(resolved).to eq(
          CopilotHistory::Types::ResolvedHistoryRoot.new(
            root_path: root,
            current_root: root.join("session-state"),
            legacy_root: root.join("history-session-state")
          )
        )
      end
    end

    # 概要・目的: 「falls back to ~/.copilot when COPILOT_HOME is not set」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「falls back to ~/.copilot when COPILOT_HOME is not set」の条件・入力・操作を実行する。
    # 期待値: ~/.copilot when COPILOT_HOME is not set に fallback すること。
    it "falls back to ~/.copilot when COPILOT_HOME is not set" do
      Dir.mktmpdir("copilot-history-home") do |home|
        with_copilot_history_fixture("current_valid") do |fixture_root|
          copilot_root = Pathname.new(home).join(".copilot")
          FileUtils.cp_r("#{fixture_root}/.", copilot_root)

          ENV.delete("COPILOT_HOME")
          ENV["HOME"] = home

          resolved = described_class.new.call

          expect(resolved).to eq(
            CopilotHistory::Types::ResolvedHistoryRoot.new(
              root_path: copilot_root,
              current_root: copilot_root.join("session-state"),
              legacy_root: copilot_root.join("history-session-state")
            )
          )
        end
      end
    end

    # 概要・目的: 「returns root_missing when the resolved root does not exist」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns root_missing when the resolved root does not exist」の条件・入力・操作を実行する。
    # 期待値: root_missing when the resolved root does not exist を返すこと。
    it "returns root_missing when the resolved root does not exist" do
      Dir.mktmpdir("copilot-history-home") do |home|
        ENV.delete("COPILOT_HOME")
        ENV["HOME"] = home

        failure = described_class.new.call

        expect(failure).to eq(
          CopilotHistory::Types::ReadFailure.new(
            code: CopilotHistory::Errors::ReadErrorCode::ROOT_MISSING,
            path: Pathname.new(home).join(".copilot"),
            message: "history root does not exist"
          )
        )
      end
    end

    # 概要・目的: 「returns root_unreadable when the resolved path is not a directory」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns root_unreadable when the resolved path is not a directory」の条件・入力・操作を実行する。
    # 期待値: root_unreadable when the resolved path is not a directory を返すこと。
    it "returns root_unreadable when the resolved path is not a directory" do
      Dir.mktmpdir("copilot-history-root") do |dir|
        root_path = Pathname.new(dir).join("copilot-home.txt")
        root_path.write("not a directory")
        ENV["COPILOT_HOME"] = root_path.to_s

        failure = described_class.new.call

        expect(failure).to eq(
          CopilotHistory::Types::ReadFailure.new(
            code: CopilotHistory::Errors::ReadErrorCode::ROOT_UNREADABLE,
            path: root_path,
            message: "history root is not a directory"
          )
        )
      end
    end

    # 概要・目的: 「returns root_permission_denied when the root directory cannot be traversed」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「returns root_permission_denied when the root directory cannot be traversed」の条件・入力・操作を実行する。
    # 期待値: root_permission_denied when the root directory cannot be traversed を返すこと。
    it "returns root_permission_denied when the root directory cannot be traversed" do
      with_copilot_history_fixture("current_valid") do |root|
        ENV["COPILOT_HOME"] = root.to_s

        with_permission_denied(root) do
          failure = described_class.new.call

          expect(failure).to eq(
            CopilotHistory::Types::ReadFailure.new(
              code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
              path: root,
              message: "history root is not accessible"
            )
          )
        end
      end
    end
  end
end

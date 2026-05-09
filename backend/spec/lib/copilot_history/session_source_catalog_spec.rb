require "rails_helper"

RSpec.describe CopilotHistory::SessionSourceCatalog, :copilot_history do
  describe "#call" do
    # 概要・目的: 「enumerates current session directories as source descriptors」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「enumerates current session directories as source descriptors」の条件・入力・操作を実行する。
    # 期待値: 「enumerates current session directories as source descriptors」で示す状態または振る舞いが成立すること。
    it "enumerates current session directories as source descriptors" do
      with_copilot_history_fixture("current_valid") do |root|
        resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
          root_path: root,
          current_root: root.join("session-state"),
          legacy_root: root.join("history-session-state")
        )

        sources = described_class.new.call(resolved_root)

        expect(sources).to eq(
          [
            CopilotHistory::Types::SessionSource.new(
              format: :current,
              session_id: "current-valid",
              source_path: root.join("session-state/current-valid"),
              artifact_paths: {
                workspace: root.join("session-state/current-valid/workspace.yaml"),
                events: root.join("session-state/current-valid/events.jsonl")
              }
            )
          ]
        )
      end
    end

    # 概要・目的: 「enumerates legacy session files as source descriptors」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「enumerates legacy session files as source descriptors」の条件・入力・操作を実行する。
    # 期待値: 「enumerates legacy session files as source descriptors」で示す状態または振る舞いが成立すること。
    it "enumerates legacy session files as source descriptors" do
      with_copilot_history_fixture("legacy_valid") do |root|
        resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
          root_path: root,
          current_root: root.join("session-state"),
          legacy_root: root.join("history-session-state")
        )

        sources = described_class.new.call(resolved_root)

        expect(sources).to eq(
          [
            CopilotHistory::Types::SessionSource.new(
              format: :legacy,
              session_id: "legacy-valid",
              source_path: root.join("history-session-state/legacy-valid.json"),
              artifact_paths: {
                source: root.join("history-session-state/legacy-valid.json")
              }
            )
          ]
        )
      end
    end

    # 概要・目的: 「returns both current and legacy sources in a stable order for mixed roots」を通じて、DB
    #   保存・validation・一意性制約を検証する。
    # テストケース: 「returns both current and legacy sources in a stable order for mixed roots」の条件・入力・操作を実行する。
    # 期待値: both current and legacy sources in a stable order for mixed roots を返すこと。
    it "returns both current and legacy sources in a stable order for mixed roots" do
      with_copilot_history_fixture("mixed_root") do |root|
        resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
          root_path: root,
          current_root: root.join("session-state"),
          legacy_root: root.join("history-session-state")
        )

        sources = described_class.new.call(resolved_root)

        expect(sources.map(&:format)).to eq(%i[current legacy])
        expect(sources.map(&:session_id)).to eq(%w[current-mixed legacy-mixed])
        expect(sources.map(&:source_path)).to eq(
          [
            root.join("session-state/current-mixed"),
            root.join("history-session-state/legacy-mixed.json")
          ]
        )
      end
    end

    # 概要・目的: 「raises a controlled access error when session-state cannot be enumerated」を通じて、hook
    #   の状態遷移と非同期制御を検証する。
    # テストケース: 「raises a controlled access error when session-state cannot be enumerated」の条件・入力・操作を実行する。
    # 期待値: 「raises a controlled access error when session-state cannot be enumerated」で示す状態または振る舞いが成立すること。
    it "raises a controlled access error when session-state cannot be enumerated" do
      with_copilot_history_fixture("current_valid") do |root|
        resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
          root_path: root,
          current_root: root.join("session-state"),
          legacy_root: root.join("history-session-state")
        )

        with_permission_denied(resolved_root.current_root) do
          expect do
            described_class.new.call(resolved_root)
          end.to raise_error(
            CopilotHistory::SessionSourceCatalog::SourceAccessError
          ) { |error|
            expect(error.failure).to eq(
              CopilotHistory::Types::ReadFailure.new(
                code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
                path: resolved_root.current_root,
                message: "history source directory is not accessible"
              )
            )
          }
        end
      end
    end

    # 概要・目的: 「raises a controlled access error when history-session-state cannot be enumerated」を通じて、検索・日付条件と
    #   query 組み立てを検証する。
    # テストケース: 「raises a controlled access error when history-session-state cannot be
    #   enumerated」の条件・入力・操作を実行する。
    # 期待値: 「raises a controlled access error when history-session-state cannot be
    #   enumerated」で示す状態または振る舞いが成立すること。
    it "raises a controlled access error when history-session-state cannot be enumerated" do
      with_copilot_history_fixture("legacy_valid") do |root|
        resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
          root_path: root,
          current_root: root.join("session-state"),
          legacy_root: root.join("history-session-state")
        )

        with_permission_denied(resolved_root.legacy_root) do
          expect do
            described_class.new.call(resolved_root)
          end.to raise_error(
            CopilotHistory::SessionSourceCatalog::SourceAccessError
          ) { |error|
            expect(error.failure).to eq(
              CopilotHistory::Types::ReadFailure.new(
                code: CopilotHistory::Errors::ReadErrorCode::ROOT_PERMISSION_DENIED,
                path: resolved_root.legacy_root,
                message: "history source directory is not accessible"
              )
            )
          }
        end
      end
    end
  end
end

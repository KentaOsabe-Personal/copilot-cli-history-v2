require "rails_helper"

RSpec.describe CopilotHistory::Api::Presenters::IssuePresenter do
  describe "#call" do
    subject(:presenter) { described_class.new }

    # 概要・目的: 「maps session-level issues to the shared JSON-compatible payload」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「maps session-level issues to the shared JSON-compatible payload」の条件・入力・操作を実行する。
    # 期待値: session-level issues が the shared JSON-compatible payload に変換されること。
    it "maps session-level issues to the shared JSON-compatible payload" do
      issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_PARSE_FAILED,
        message: "workspace.yaml could not be parsed",
        source_path: "/tmp/copilot/workspace.yaml",
        severity: :error
      )

      expect(presenter.call(issue:)).to eq(
        code: "current.workspace_parse_failed",
        severity: "error",
        message: "workspace.yaml could not be parsed",
        source_path: "/tmp/copilot/workspace.yaml",
        scope: "session",
        event_sequence: nil
      )
    end

    # 概要・目的: 「maps event-level issues to the same payload with event location fields」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「maps event-level issues to the same payload with event location fields」の条件・入力・操作を実行する。
    # 期待値: event-level issues が the same payload with event location fields に変換されること。
    it "maps event-level issues to the same payload with event location fields" do
      issue = CopilotHistory::Types::ReadIssue.new(
        code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
        message: "event payload matched partially",
        source_path: "/tmp/copilot/events.jsonl",
        sequence: 7,
        severity: :warning
      )

      expect(presenter.call(issue:)).to eq(
        code: "event.partial_mapping",
        severity: "warning",
        message: "event payload matched partially",
        source_path: "/tmp/copilot/events.jsonl",
        scope: "event",
        event_sequence: 7
      )
    end
  end
end

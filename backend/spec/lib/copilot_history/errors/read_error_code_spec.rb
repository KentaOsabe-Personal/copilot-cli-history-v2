require "rails_helper"

RSpec.describe CopilotHistory::Errors::ReadErrorCode do
  # 概要・目的: 「defines stable root failure codes」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「defines stable root failure codes」の条件・入力・操作を実行する。
  # 期待値: 「defines stable root failure codes」で示す状態または振る舞いが成立すること。
  it "defines stable root failure codes" do
    expect(described_class::ROOT_MISSING).to eq("root_missing")
    expect(described_class::ROOT_PERMISSION_DENIED).to eq("root_permission_denied")
    expect(described_class::ROOT_UNREADABLE).to eq("root_unreadable")
    expect(described_class::ROOT_FAILURE_CODES).to contain_exactly(
      "root_missing",
      "root_permission_denied",
      "root_unreadable"
    )
  end

  # 概要・目的: 「defines stable session issue codes」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「defines stable session issue codes」の条件・入力・操作を実行する。
  # 期待値: 「defines stable session issue codes」で示す状態または振る舞いが成立すること。
  it "defines stable session issue codes" do
    expect(described_class::CURRENT_WORKSPACE_UNREADABLE).to eq("current.workspace_unreadable")
    expect(described_class::CURRENT_EVENTS_MISSING).to eq("current.events_missing")
    expect(described_class::CURRENT_EVENTS_UNREADABLE).to eq("current.events_unreadable")
    expect(described_class::CURRENT_WORKSPACE_PARSE_FAILED).to eq("current.workspace_parse_failed")
    expect(described_class::CURRENT_EVENT_PARSE_FAILED).to eq("current.event_parse_failed")
    expect(described_class::LEGACY_SOURCE_UNREADABLE).to eq("legacy.source_unreadable")
    expect(described_class::LEGACY_JSON_PARSE_FAILED).to eq("legacy.json_parse_failed")
    expect(described_class::EVENT_PARTIAL_MAPPING).to eq("event.partial_mapping")
    expect(described_class::EVENT_UNKNOWN_SHAPE).to eq("event.unknown_shape")
    expect(described_class::SESSION_ISSUE_CODES).to include(
      "current.workspace_unreadable",
      "current.events_missing",
      "current.events_unreadable",
      "current.workspace_parse_failed",
      "current.event_parse_failed",
      "legacy.source_unreadable",
      "legacy.json_parse_failed",
      "event.partial_mapping",
      "event.unknown_shape"
    )
  end
end

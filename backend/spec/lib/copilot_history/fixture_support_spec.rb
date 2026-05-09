require "rails_helper"

RSpec.describe "Copilot history fixture support", :copilot_history do
  # 概要・目的: 「provides raw current and legacy fixture files from a mixed root」を通じて、reader と fixture
  #   の読取・劣化時の扱いを検証する。
  # テストケース: 「provides raw current and legacy fixture files from a mixed root」の条件・入力・操作を実行する。
  # 期待値: 「provides raw current and legacy fixture files from a mixed root」で示す状態または振る舞いが成立すること。
  it "provides raw current and legacy fixture files from a mixed root" do
    with_copilot_history_fixture("mixed_root") do |root|
      workspace = root.join("session-state/current-mixed/workspace.yaml")
      events = root.join("session-state/current-mixed/events.jsonl")
      legacy = root.join("history-session-state/legacy-mixed.json")

      expect(workspace.read).to include("session_id: current-mixed")
      expect(events.each_line.map(&:strip)).to include(
        a_string_including("\"type\":\"user_message\""),
        a_string_including("\"type\":\"mystery-event\"")
      )
      expect(legacy.read).to include("\"sessionId\": \"legacy-mixed\"")
    end
  end

  # 概要・目的: 「provides representative current schema fixture files for canonical message and detail
  #   scenarios」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
  # テストケース: 「provides representative current schema fixture files for canonical message and detail
  #   scenarios」の条件・入力・操作を実行する。
  # 期待値: 「provides representative current schema fixture files for canonical message and detail
  #   scenarios」で示す状態または振る舞いが成立すること。
  it "provides representative current schema fixture files for canonical message and detail scenarios" do
    with_copilot_history_fixture("current_schema_valid") do |root|
      workspace = root.join("session-state/current-schema-valid/workspace.yaml")
      events = root.join("session-state/current-schema-valid/events.jsonl")
      lines = events.each_line.map(&:strip)

      expect(workspace.read).to include("session_id: current-schema-valid")
      expect(lines).to include(
        a_string_including("\"type\":\"system.message\""),
        a_string_including("\"type\":\"user.message\""),
        a_string_including("\"type\":\"assistant.message\""),
        a_string_including("\"type\":\"assistant.turn_start\""),
        a_string_including("\"type\":\"tool.execution_start\""),
        a_string_including("\"toolRequests\":[")
      )
    end
  end

  # 概要・目的: 「provides degraded current schema fixture files for partial tool data, unknown events, and invalid
  #   jsonl」を通じて、DB 保存・validation・一意性制約を検証する。
  # テストケース: 「provides degraded current schema fixture files for partial tool data, unknown events, and invalid
  #   jsonl」の条件・入力・操作を実行する。
  # 期待値: 「provides degraded current schema fixture files for partial tool data, unknown events, and invalid
  #   jsonl」で示す状態または振る舞いが成立すること。
  it "provides degraded current schema fixture files for partial tool data, unknown events, and invalid jsonl" do
    with_copilot_history_fixture("current_schema_degraded") do |root|
      workspace = root.join("session-state/current-schema-degraded/workspace.yaml")
      events = root.join("session-state/current-schema-degraded/events.jsonl")
      lines = events.each_line.map(&:rstrip)

      expect(workspace.read).to include("session_id: current-schema-degraded")
      expect(lines).to include(
        a_string_including("\"type\":\"assistant.message\""),
        a_string_including("\"toolRequests\":[{\"arguments\":"),
        a_string_including("\"type\":\"hook.start\""),
        a_string_including("\"type\":\"mystery.event\"")
      )
      expect { JSON.parse(lines.last) }.to raise_error(JSON::ParserError)
    end
  end

  # 概要・目的: 「can apply and restore permission restrictions on copied fixture artifacts」を通じて、DB
  #   保存・validation・一意性制約を検証する。
  # テストケース: 「can apply and restore permission restrictions on copied fixture artifacts」の条件・入力・操作を実行する。
  # 期待値: 「can apply and restore permission restrictions on copied fixture artifacts」で示す状態または振る舞いが成立すること。
  it "can apply and restore permission restrictions on copied fixture artifacts" do
    with_copilot_history_fixture("current_unreadable") do |root|
      target = root.join("session-state/current-unreadable/events.jsonl")
      original_mode = target.stat.mode & 0o777

      with_permission_denied(target) do |restricted_path|
        expect(restricted_path.stat.mode & 0o777).to eq(0o000)
      end

      expect(target.stat.mode & 0o777).to eq(original_mode)
    end
  end
end

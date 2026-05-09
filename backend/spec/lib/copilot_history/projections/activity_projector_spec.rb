require "rails_helper"

RSpec.describe CopilotHistory::Projections::ActivityProjector, :copilot_history do
  subject(:projector) { described_class.new }

  describe "#call" do
    # 概要・目的: 「projects system, detail, and unknown events separately from conversation messages」を通じて、reader と
    #   fixture の読取・劣化時の扱いを検証する。
    # テストケース: 「projects system, detail, and unknown events separately from conversation
    #   messages」の条件・入力・操作を実行する。
    # 期待値: 「projects system, detail, and unknown events separately from conversation
    #   messages」で示す状態または振る舞いが成立すること。
    it "projects system, detail, and unknown events separately from conversation messages" do
      with_copilot_history_fixture("current_schema_valid") do |root|
        session = read_first_current_session(root)

        projection = projector.call(session)

        expect(projection.entries.map { |entry| [ entry.sequence, entry.category, entry.title ] }).to eq(
          [
            [ 1, "system", "system.message" ],
            [ 3, "assistant_turn", "assistant.turn_start" ],
            [ 6, "tool_execution", "tool.execution_start" ],
            [ 7, "tool_execution", "tool.execution_complete" ],
            [ 8, "skill", "skill.invoked" ],
            [ 9, "assistant_turn", "assistant.turn_end" ]
          ]
        )
        expect(projection.entries).to all(have_attributes(raw_available: true))
      end
    end

    # 概要・目的: 「keeps unknown and partial issue traceability on activity entries」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「keeps unknown and partial issue traceability on activity entries」の条件・入力・操作を実行する。
    # 期待値: unknown が維持され、partial issue traceability on activity entriesこと。
    it "keeps unknown and partial issue traceability on activity entries" do
      with_copilot_history_fixture("current_schema_degraded") do |root|
        session = read_first_current_session(root)

        projection = projector.call(session)

        hook = projection.entries.find { |entry| entry.category == "hook" }
        unknown = projection.entries.find { |entry| entry.category == "unknown" }

        expect(hook).to have_attributes(
          sequence: 3,
          title: "hook.start",
          summary: "before-tool / *",
          mapping_status: :complete,
          raw_available: true
        )
        expect(unknown).to have_attributes(
          sequence: 4,
          title: "mystery.event",
          raw_type: "mystery.event",
          mapping_status: :complete,
          raw_available: true
        )
        expect(unknown.issues.map(&:code)).to eq([ "event.unknown_shape" ])
      end
    end
  end

  def read_first_current_session(root)
    resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
      root_path: root,
      current_root: root.join("session-state"),
      legacy_root: root.join("history-session-state")
    )
    source = CopilotHistory::SessionSourceCatalog.new.call(resolved_root).find { |candidate| candidate.format == :current }

    CopilotHistory::CurrentSessionReader.new.call(source)
  end
end

require "rails_helper"

RSpec.describe "CopilotHistory session projection summary", :copilot_history do
  # 概要・目的: 「derives conversation presence, preview, message count, and activity count from normalized
  #   sessions」を通じて、正規化・projection・presenter の変換契約を検証する。
  # テストケース: 「derives conversation presence, preview, message count, and activity count from normalized
  #   sessions」の条件・入力・操作を実行する。
  # 期待値: 「derives conversation presence, preview, message count, and activity count from normalized
  #   sessions」で示す状態または振る舞いが成立すること。
  it "derives conversation presence, preview, message count, and activity count from normalized sessions" do
    with_copilot_history_fixture("current_schema_mixed_root") do |root|
      resolved_root = CopilotHistory::Types::ResolvedHistoryRoot.new(
        root_path: root,
        current_root: root.join("session-state"),
        legacy_root: root.join("history-session-state")
      )
      sessions = CopilotHistory::SessionSourceCatalog.new.call(resolved_root).map do |source|
        case source.format
        when :current
          CopilotHistory::CurrentSessionReader.new.call(source)
        when :legacy
          CopilotHistory::LegacySessionReader.new.call(source)
        end
      end
      conversation_projector = CopilotHistory::Projections::ConversationProjector.new
      activity_projector = CopilotHistory::Projections::ActivityProjector.new

      summaries = sessions.to_h do |session|
        conversation = conversation_projector.call(session)
        activity = activity_projector.call(session)

        [
          session.session_id,
          conversation.summary.with(activity_count: activity.entries.length)
        ]
      end

      expect(summaries.fetch("current-schema-mixed")).to have_attributes(
        has_conversation: true,
        message_count: 2,
        preview: "current mixed question",
        activity_count: 0
      )
      expect(summaries.fetch("legacy-schema-mixed")).to have_attributes(
        has_conversation: true,
        message_count: 2,
        preview: "legacy mixed question",
        activity_count: 0
      )
    end
  end
end

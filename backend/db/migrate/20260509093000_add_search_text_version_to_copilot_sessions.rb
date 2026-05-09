class AddSearchTextVersionToCopilotSessions < ActiveRecord::Migration[8.1]
  SEARCH_TEXT_VERSION = 2

  class MigrationCopilotSession < ActiveRecord::Base
    self.table_name = "copilot_sessions"
  end

  def up
    add_column :copilot_sessions, :search_text_version, :integer, null: false, default: 0

    say_with_time "Backfill conversation-focused search text" do
      MigrationCopilotSession.reset_column_information

      MigrationCopilotSession.find_each do |record|
        record.update_columns(
          search_text: build_search_text(
            summary_payload: record.summary_payload || {},
            detail_payload: record.detail_payload || {}
          ),
          search_text_version: SEARCH_TEXT_VERSION
        )
      end
    end
  end

  def down
    remove_column :copilot_sessions, :search_text_version
  end

  private

  def build_search_text(summary_payload:, detail_payload:)
    values = []
    values << hash_value(hash_value(summary_payload, :conversation_summary), :preview)

    conversation = hash_value(detail_payload, :conversation)
    values.concat(issue_values(array_value(detail_payload, :issues)))
    values.concat(conversation_values(conversation))

    values
      .filter_map { |value| normalize(value) }
      .uniq
      .join("\n")
  end

  def conversation_values(conversation)
    return [] unless conversation.is_a?(Hash)

    summary = hash_value(conversation, :summary)
    entries = array_value(conversation, :entries)

    [
      hash_value(summary, :preview),
      *entries.flat_map { |entry| conversation_entry_values(entry) }
    ]
  end

  def conversation_entry_values(entry)
    return [] unless entry.is_a?(Hash)

    [
      hash_value(entry, :content),
      *issue_values(array_value(entry, :issues))
    ]
  end

  def issue_values(issues)
    issues.flat_map do |issue|
      next [] unless issue.is_a?(Hash)

      [
        hash_value(issue, :code),
        hash_value(issue, :message)
      ]
    end
  end

  def array_value(hash, key)
    value = hash_value(hash, key)
    value.is_a?(Array) ? value : []
  end

  def hash_value(hash, key)
    return nil unless hash.is_a?(Hash)

    hash[key] || hash[key.to_s]
  end

  def normalize(value)
    return nil if value.nil?

    text = value.to_s.gsub(/[[:space:]]+/, " ").strip
    text.empty? ? nil : text
  end
end

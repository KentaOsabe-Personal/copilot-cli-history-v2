module CopilotHistory
  module Persistence
    class SessionSearchTextBuilder
      VERSION = 2

      def call(summary_payload:, detail_payload:, metadata:)
        values = []
        values.concat(summary_values(summary_payload))
        values.concat(detail_values(detail_payload))

        values
          .filter_map { |value| normalize(value) }
          .uniq
          .join("\n")
      end

      private

      def summary_values(payload)
        summary = hash_value(payload, :conversation_summary)

        [
          hash_value(summary, :preview)
        ]
      end

      def detail_values(payload)
        conversation = hash_value(payload, :conversation)

        [
          *issue_values(array_value(payload, :issues)),
          *conversation_values(conversation)
        ]
      end

      def conversation_values(conversation)
        return [] unless conversation.is_a?(Hash)

        entries = array_value(conversation, :entries)
        summary = hash_value(conversation, :summary)

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
  end
end

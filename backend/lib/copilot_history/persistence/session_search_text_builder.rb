module CopilotHistory
  module Persistence
    class SessionSearchTextBuilder
      def call(summary_payload:, detail_payload:, metadata:)
        values = []
        values.concat(summary_values(summary_payload))
        values.concat(detail_values(detail_payload))
        values.concat(metadata_values(metadata))

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
        activity = hash_value(payload, :activity)

        [
          hash_value(payload, :selected_model),
          *work_context_values(hash_value(payload, :work_context)),
          *issue_values(array_value(payload, :issues)),
          *conversation_values(conversation),
          *activity_values(activity),
          *timeline_values(array_value(payload, :timeline))
        ]
      end

      def metadata_values(metadata)
        [
          hash_value(metadata, :cwd),
          hash_value(metadata, :git_root),
          hash_value(metadata, :repository),
          hash_value(metadata, :branch),
          hash_value(metadata, :selected_model)
        ]
      end

      def work_context_values(context)
        return [] unless context.is_a?(Hash)

        %i[cwd git_root repository branch].map { |key| hash_value(context, key) }
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
          *tool_call_values(array_value(entry, :tool_calls)),
          *issue_values(array_value(entry, :issues))
        ]
      end

      def activity_values(activity)
        return [] unless activity.is_a?(Hash)

        array_value(activity, :entries).flat_map do |entry|
          next [] unless entry.is_a?(Hash)

          [
            hash_value(entry, :title),
            hash_value(entry, :summary),
            *issue_values(array_value(entry, :issues))
          ]
        end
      end

      def timeline_values(entries)
        entries.flat_map do |entry|
          next [] unless entry.is_a?(Hash)

          [
            hash_value(entry, :content),
            *tool_call_values(array_value(entry, :tool_calls)),
            *issue_values(array_value(entry, :issues))
          ]
        end
      end

      def tool_call_values(tool_calls)
        tool_calls.flat_map do |tool_call|
          next [] unless tool_call.is_a?(Hash)

          [
            hash_value(tool_call, :name),
            hash_value(tool_call, :arguments_preview)
          ]
        end
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

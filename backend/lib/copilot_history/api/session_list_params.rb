module CopilotHistory
  module Api
    class SessionListParams
      INVALID_CODE = "invalid_session_list_query"
      INVALID_MESSAGE = "session list query is invalid"
      MAX_SEARCH_LENGTH = 200

      Result = Data.define(:from_time, :to_time, :limit, :search_term)

      def call(params:, now: Time.current)
        from_time = parse_time(params_value(params, :from), field: "from", boundary: :start)
        return from_time if invalid?(from_time)

        to_time = parse_time(params_value(params, :to), field: "to", boundary: :end)
        return to_time if invalid?(to_time)

        if from_time.nil? && to_time.nil?
          from_time = now - 30.days
          to_time = now
        end

        return invalid(field: "range", reason: "from_after_to") if from_time && to_time && from_time > to_time

        limit = parse_limit(params_value(params, :limit))
        return limit if invalid?(limit)

        search_term = parse_search(params_value(params, :search))
        return search_term if invalid?(search_term)

        Result.new(from_time:, to_time:, limit:, search_term:)
      end

      private

      DATE_ONLY_PATTERN = /\A\d{4}-\d{2}-\d{2}\z/

      def params_value(params, key)
        params[key] || params[key.to_s]
      end

      def parse_time(value, field:, boundary:)
        return nil if value.blank?

        raw_value = value.to_s
        if DATE_ONLY_PATTERN.match?(raw_value)
          date = Date.iso8601(raw_value)
          time = date.in_time_zone
          return boundary == :start ? time.beginning_of_day : time.end_of_day
        end

        Time.zone.iso8601(raw_value)
      rescue ArgumentError
        invalid(field:, reason: "invalid_datetime", value: raw_value)
      end

      def parse_limit(value)
        return nil if value.blank?

        raw_value = value.to_s
        return invalid(field: "limit", reason: "positive_integer_required", value: raw_value) unless /\A[1-9]\d*\z/.match?(raw_value)

        raw_value.to_i
      end

      def parse_search(value)
        return nil if value.nil?

        raw_value = value.to_s
        return invalid(field: "search", reason: "control_character", value: raw_value) if display_hostile_control_character?(raw_value)

        normalized = raw_value.strip.gsub(/\s+/, " ")
        return nil if normalized.empty?
        return invalid(field: "search", reason: "too_long", value: raw_value) if normalized.length > MAX_SEARCH_LENGTH

        normalized
      end

      def display_hostile_control_character?(value)
        value.match?(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/)
      end

      def invalid?(value)
        value.is_a?(Types::SessionIndexResult::Invalid)
      end

      def invalid(field:, reason:, value: nil)
        details = { field:, reason: }
        details[:value] = value unless value.nil?

        Types::SessionIndexResult::Invalid.new(
          code: INVALID_CODE,
          message: INVALID_MESSAGE,
          details:
        )
      end
    end
  end
end

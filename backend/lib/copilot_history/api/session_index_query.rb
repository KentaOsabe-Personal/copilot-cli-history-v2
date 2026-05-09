module CopilotHistory
  module Api
    class SessionIndexQuery
      Candidate = Data.define(:session_id, :display_time)

      def initialize(model: CopilotSession)
        @model = model
      end

      def call(from_time: nil, to_time: nil, limit: nil, search_term: nil)
        ordered_session_ids = ordered_candidates(from_time:, to_time:, limit:, search_term:).map(&:session_id)
        payloads_by_session_id = model
          .where(session_id: ordered_session_ids)
          .pluck(:session_id, :summary_payload)
          .to_h
        data = ordered_session_ids.filter_map { |session_id| payloads_by_session_id[session_id] }

        Types::SessionIndexResult::Success.new(
          data: data,
          meta: {
            count: data.count,
            partial_results: data.any? { |payload| payload["degraded"] == true }
          }
        )
      end

      private

      attr_reader :model

      def ordered_candidates(from_time:, to_time:, limit:, search_term:)
        candidates = updated_source_candidates(from_time:, to_time:, search_term:) + created_source_candidates(from_time:, to_time:, search_term:)
        sorted_candidates = candidates.sort_by { |candidate| [ -candidate.display_time.to_f, candidate.session_id ] }

        limit ? sorted_candidates.first(limit) : sorted_candidates
      end

      def updated_source_candidates(from_time:, to_time:, search_term:)
        scope = search_scope(search_term).where.not(updated_at_source: nil)
        scope = scope.where(updated_at_source: from_time..) if from_time
        scope = scope.where(updated_at_source: ..to_time) if to_time

        scope.pluck(:session_id, :updated_at_source).map do |session_id, updated_at_source|
          Candidate.new(session_id:, display_time: updated_at_source)
        end
      end

      def created_source_candidates(from_time:, to_time:, search_term:)
        scope = search_scope(search_term).where(updated_at_source: nil).where.not(created_at_source: nil)
        scope = scope.where(created_at_source: from_time..) if from_time
        scope = scope.where(created_at_source: ..to_time) if to_time

        scope.pluck(:session_id, :created_at_source).map do |session_id, created_at_source|
          Candidate.new(session_id:, display_time: created_at_source)
        end
      end

      def search_scope(search_term)
        scope = model.all
        return scope if search_term.blank?

        escaped_term = ActiveRecord::Base.sanitize_sql_like(search_term, "!")
        scope.where("search_text LIKE ? ESCAPE '!'", "%#{escaped_term}%")
      end
    end
  end
end

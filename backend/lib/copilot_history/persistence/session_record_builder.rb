module CopilotHistory
  module Persistence
    class SessionRecordBuilder
      def initialize(
        summary_presenter: CopilotHistory::Api::Presenters::SessionIndexPresenter.new,
        detail_presenter: CopilotHistory::Api::Presenters::SessionDetailPresenter.new,
        fingerprint_builder: SourceFingerprintBuilder.new,
        search_text_builder: SessionSearchTextBuilder.new
      )
        @summary_presenter = summary_presenter
        @detail_presenter = detail_presenter
        @fingerprint_builder = fingerprint_builder
        @search_text_builder = search_text_builder
      end

      def call(session:, indexed_at: Time.current, source_fingerprint: nil)
        summary_payload = build_summary_payload(session)
        detail_payload = build_detail_payload(session)
        conversation_summary = summary_payload.fetch(:conversation_summary, {})
        scalar_metadata = metadata_for(session)

        {
          session_id: session.session_id,
          source_format: session.source_format.to_s,
          source_state: session.source_state.to_s,
          created_at_source: session.created_at,
          updated_at_source: session.updated_at,
          cwd: path_or_nil(session.cwd),
          git_root: path_or_nil(session.git_root),
          repository: session.repository,
          branch: session.branch,
          selected_model: session.selected_model,
          event_count: session.events.length,
          message_snapshot_count: session.message_snapshots.length,
          issue_count: session.issues.length,
          degraded: session.issues.any?,
          conversation_preview: conversation_summary[:preview],
          search_text: search_text_builder.call(
            summary_payload: summary_payload,
            detail_payload: detail_payload,
            metadata: scalar_metadata
          ),
          message_count: conversation_summary.fetch(:message_count, 0),
          activity_count: conversation_summary.fetch(:activity_count, 0),
          source_paths: stringify_source_paths(session.source_paths),
          source_fingerprint: source_fingerprint || fingerprint_builder.call(source_paths: session.source_paths),
          summary_payload: summary_payload,
          detail_payload: detail_payload,
          indexed_at: indexed_at
        }
      end

      private

      attr_reader :summary_presenter, :detail_presenter, :fingerprint_builder, :search_text_builder

      def metadata_for(session)
        {
          cwd: path_or_nil(session.cwd),
          git_root: path_or_nil(session.git_root),
          repository: session.repository,
          branch: session.branch,
          selected_model: session.selected_model
        }
      end

      def build_summary_payload(session)
        result = CopilotHistory::Types::ReadResult::Success.new(root: nil, sessions: [ session ])

        summary_presenter.call(result: result).fetch(:data).fetch(0)
      end

      def build_detail_payload(session)
        result = CopilotHistory::Api::Types::SessionLookupResult::Found.new(root: nil, session: session)

        detail_presenter.call(result: result, include_raw: false).fetch(:data)
      end

      def stringify_source_paths(source_paths)
        source_paths
          .sort_by { |role, _path| role.to_s }
          .to_h { |role, path| [ role.to_s, path_or_nil(path) ] }
      end

      def path_or_nil(value)
        value&.to_s
      end
    end
  end
end

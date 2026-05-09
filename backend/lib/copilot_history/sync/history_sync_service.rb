module CopilotHistory
  module Sync
    class HistorySyncService
      RUNNING_LOCK_KEY = "history_sync".freeze
      PERSISTENCE_FAILURE_CODE = "history_sync_failed"
      PERSISTENCE_FAILURE_MESSAGE = "history sync failed"

      def initialize(
        reader: CopilotHistory::SessionCatalogReader.new,
        fingerprint_builder: CopilotHistory::Persistence::SourceFingerprintBuilder.new,
        record_builder: CopilotHistory::Persistence::SessionRecordBuilder.new,
        clock: Time
      )
        @reader = reader
        @fingerprint_builder = fingerprint_builder
        @record_builder = record_builder
        @clock = clock
      end

      def call
        running_run = existing_running_run
        return SyncResult::Conflict.new(running_run:) if running_run

        sync_run = start_running_run_or_conflict
        return sync_run if sync_run.is_a?(SyncResult::Conflict)

        read_result = reader.call
        return handle_root_failure(sync_run:, failure: read_result.failure) if read_result.failure?

        persist_success(sync_run:, sessions: read_result.sessions)
      end

      private

      attr_reader :reader, :fingerprint_builder, :record_builder, :clock

      def start_running_run
        HistorySyncRun.create!(
          status: "running",
          started_at: current_time,
          running_lock_key: RUNNING_LOCK_KEY
        )
      end

      def start_running_run_or_conflict
        start_running_run
      rescue ActiveRecord::RecordNotUnique
        running_run = existing_running_run
        raise unless running_run

        SyncResult::Conflict.new(running_run:)
      end

      def existing_running_run
        HistorySyncRun.find_by(running_lock_key: RUNNING_LOCK_KEY) ||
          HistorySyncRun.where(status: "running").order(:started_at, :id).first
      end

      def handle_root_failure(sync_run:, failure:)
        sync_run.update!(
          status: "failed",
          finished_at: current_time,
          failed_count: 1,
          failure_summary: failure.message,
          running_lock_key: nil
        )

        SyncResult::Failed.new(
          sync_run: sync_run.reload,
          code: failure.code,
          message: failure.message,
          details: { path: failure.path.to_s }
        )
      end

      def persist_success(sync_run:, sessions:)
        counts = nil

        ActiveRecord::Base.transaction do
          counts = persist_sessions(sessions)
          sync_run.update!(
            status: counts.fetch(:degraded_count).positive? ? "completed_with_issues" : "succeeded",
            finished_at: current_time,
            processed_count: counts.fetch(:processed_count),
            inserted_count: counts.fetch(:inserted_count),
            updated_count: counts.fetch(:updated_count),
            saved_count: counts.fetch(:saved_count),
            skipped_count: counts.fetch(:skipped_count),
            failed_count: 0,
            degraded_count: counts.fetch(:degraded_count),
            degradation_summary: degradation_summary(counts.fetch(:degraded_count)),
            running_lock_key: nil
          )
        end

        SyncResult::Succeeded.new(sync_run: sync_run.reload)
      rescue StandardError => error
        handle_persistence_failure(sync_run:, error:)
      end

      def persist_sessions(sessions)
        counts = {
          processed_count: sessions.length,
          inserted_count: 0,
          updated_count: 0,
          saved_count: 0,
          skipped_count: 0,
          degraded_count: sessions.count { |session| degraded_session?(session) }
        }

        sessions.each do |session|
          fingerprint = fingerprint_builder.call(source_paths: session.source_paths)
          existing = CopilotSession.find_by(session_id: session.session_id)

          if existing.nil?
            CopilotSession.create!(record_attributes(session:, fingerprint:))
            counts[:inserted_count] += 1
            counts[:saved_count] += 1
          elsif existing.source_fingerprint == fingerprint && search_projection_created?(existing)
            counts[:skipped_count] += 1
          else
            existing.update!(record_attributes(session:, fingerprint:))
            counts[:updated_count] += 1
            counts[:saved_count] += 1
          end
        end

        counts
      end

      def record_attributes(session:, fingerprint:)
        record_builder.call(session:, indexed_at: current_time, source_fingerprint: fingerprint)
      end

      def search_projection_created?(record)
        record.search_text_version == CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION
      end

      def handle_persistence_failure(sync_run:, error:)
        sync_run.reload.update!(
          status: "failed",
          finished_at: current_time,
          failed_count: 1,
          failure_summary: "#{error.class}: #{error.message}",
          running_lock_key: nil
        )

        SyncResult::Failed.new(
          sync_run: sync_run.reload,
          code: PERSISTENCE_FAILURE_CODE,
          message: PERSISTENCE_FAILURE_MESSAGE,
          details: { failure_class: error.class.name }
        )
      end

      def degradation_summary(degraded_count)
        return nil if degraded_count.zero?

        "#{degraded_count} sessions degraded"
      end

      def degraded_session?(session)
        session.source_state.to_s == "degraded" || session.issues.any?
      end

      def current_time
        clock.current
      end
    end
  end
end

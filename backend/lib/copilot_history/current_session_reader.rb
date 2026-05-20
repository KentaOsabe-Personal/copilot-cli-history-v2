require "json"
require "date"
require "psych"

module CopilotHistory
  class CurrentSessionReader
    def initialize(event_normalizer_class: CopilotHistory::EventNormalizer)
      @event_normalizer_class = event_normalizer_class
    end

    def call(source)
      raise ArgumentError, "source format must be current" unless source.format == :current

      workspace_metadata, workspace_issues = read_workspace(source.artifact_paths.fetch(:workspace))
      events, event_issues, events_mtime, selected_model = read_events(source)
      issues = workspace_issues + event_issues

      CopilotHistory::Types::NormalizedSession.new(
        session_id: workspace_metadata.fetch("session_id", source.session_id),
        source_format: :current,
        source_state: source_state_for(workspace_issues:, event_issues:),
        cwd: workspace_metadata["cwd"],
        git_root: workspace_metadata["git_root"],
        repository: workspace_metadata["repository"],
        branch: workspace_metadata["branch"],
        created_at: workspace_metadata["created_at"],
        updated_at: corrected_updated_at(events:, events_mtime:, workspace_metadata:),
        selected_model: selected_model,
        events: events,
        message_snapshots: [],
        issues: issues,
        source_paths: source.artifact_paths
      )
    end

    private

    attr_reader :event_normalizer_class

    def read_workspace(workspace_path)
      return [ {}, [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_UNREADABLE, "workspace.yaml is not accessible", workspace_path) ] ] unless readable_file?(workspace_path)

      payload = Psych.safe_load(workspace_path.read, permitted_classes: [ Date, Time ], aliases: false)
      unless payload.is_a?(Hash)
        return [ {}, [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_PARSE_FAILED, "workspace.yaml could not be parsed", workspace_path) ] ]
      end

      [ stringify_keys(payload), [] ]
    rescue Psych::Exception
      [ {}, [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_PARSE_FAILED, "workspace.yaml could not be parsed", workspace_path) ] ]
    rescue SystemCallError
      [ {}, [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_WORKSPACE_UNREADABLE, "workspace.yaml is not accessible", workspace_path) ] ]
    end

    def read_events(source)
      events_path = source.artifact_paths.fetch(:events)
      return [ [], [ warning_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_MISSING, "events.jsonl is missing for current session", events_path) ], nil, nil ] unless events_path.exist?
      return [ [], [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_UNREADABLE, "events.jsonl is not accessible", events_path) ], nil, nil ] unless readable_file?(events_path)

      normalizer = event_normalizer_class.new(source_path: events_path)
      events = []
      issues = []
      events_mtime = events_path.stat.mtime
      selected_model_candidate = nil

      events_path.each_line.with_index(1) do |line, sequence|
        raw_event = JSON.parse(line)
        selected_model_candidate = choose_model_candidate(selected_model_candidate, extract_model_candidate(raw_event))
        normalization_result = normalizer.call(
          raw_event: raw_event,
          source_format: source.format,
          sequence: sequence
        )

        events << normalization_result.event
        issues.concat(normalization_result.issues)
      rescue JSON::ParserError
        issues << error_issue(
          CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENT_PARSE_FAILED,
          "events.jsonl line could not be parsed",
          events_path,
          sequence: sequence
        )
      end

      selected_model = selected_model_candidate&.fetch(:value)
      [ events, issues, events_mtime, selected_model ]
    rescue SystemCallError
      [ [].freeze, [ error_issue(CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_UNREADABLE, "events.jsonl is not accessible", events_path) ], nil, nil ]
    end

    def error_issue(code, message, source_path, sequence: nil)
      CopilotHistory::Types::ReadIssue.new(
        code: code,
        message: message,
        source_path: source_path,
        sequence: sequence,
        severity: :error
      )
    end

    def warning_issue(code, message, source_path, sequence: nil)
      CopilotHistory::Types::ReadIssue.new(
        code: code,
        message: message,
        source_path: source_path,
        sequence: sequence,
        severity: :warning
      )
    end

    def source_state_for(workspace_issues:, event_issues:)
      return :degraded if workspace_issues.any?

      if event_issues.one? && event_issues.first.code == CopilotHistory::Errors::ReadErrorCode::CURRENT_EVENTS_MISSING
        return :workspace_only
      end

      event_issues.any? ? :degraded : :complete
    end

    def readable_file?(path)
      stat = path.stat

      path.file? && readable_by_process?(stat)
    rescue SystemCallError
      false
    end

    def readable_by_process?(stat)
      mode = stat.mode

      if stat.uid == Process.euid
        (mode & 0o400).positive?
      elsif process_groups.include?(stat.gid)
        (mode & 0o040).positive?
      else
        (mode & 0o004).positive?
      end
    end

    def process_groups
      @process_groups ||= [ Process.egid, *Process.groups ].uniq.freeze
    end

    def corrected_updated_at(events:, events_mtime:, workspace_metadata:)
      event_updated_at = events.filter_map(&:occurred_at).max
      event_updated_at || events_mtime || parse_time(workspace_metadata["updated_at"]) || parse_time(workspace_metadata["created_at"])
    end

    def choose_model_candidate(current_candidate, next_candidate)
      return current_candidate if next_candidate.nil?
      return next_candidate if current_candidate.nil?
      return next_candidate if next_candidate.fetch(:priority) >= current_candidate.fetch(:priority)

      current_candidate
    end

    def extract_model_candidate(raw_event)
      return nil unless raw_event.is_a?(Hash)

      data = raw_event["data"].is_a?(Hash) ? raw_event["data"] : {}
      candidate_values_for(raw_event.fetch("type", nil), data, raw_event).filter_map do |priority, candidate|
        normalized_candidate = normalize_model_candidate(candidate)
        next if normalized_candidate.nil?

        { priority: priority, value: normalized_candidate }
      end.reduce(nil) { |selected, candidate| choose_model_candidate(selected, candidate) }
    end

    def candidate_values_for(raw_type, data, raw_event)
      values = []
      values << [ 3, data["currentModel"] ] if raw_type == "session.shutdown"
      values << [ 2, data["model"] ] if raw_type == "tool.execution_complete"
      values << [ 1, data["model"] ] if raw_type == "assistant.usage"
      values << [ 0, raw_event["model"] ]
      values
    end

    def normalize_model_candidate(candidate)
      return nil unless candidate.is_a?(String)

      candidate.strip.then { |value| value.empty? ? nil : value }
    end

    def parse_time(value)
      return nil if value.nil?
      return value if value.is_a?(Time)

      Time.iso8601(value.to_s)
    rescue ArgumentError
      nil
    end

    def stringify_keys(hash)
      hash.each_with_object({}) do |(key, value), normalized|
        normalized[key.to_s] = value
      end
    end
  end
end

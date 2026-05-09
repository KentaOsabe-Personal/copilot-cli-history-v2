require "rails_helper"
require "tempfile"

RSpec.describe CopilotHistory::Sync::HistorySyncService do
  subject(:service) do
    described_class.new(
      reader: reader,
      fingerprint_builder: fingerprint_builder,
      record_builder: record_builder,
      clock: clock
    )
  end

  let(:reader) { instance_double(CopilotHistory::SessionCatalogReader) }
  let(:fingerprint_builder) { instance_double(CopilotHistory::Persistence::SourceFingerprintBuilder) }
  let(:record_builder) { instance_double(CopilotHistory::Persistence::SessionRecordBuilder) }
  let(:clock) { instance_double(Clock, current: now) }
  let(:now) { Time.zone.parse("2026-04-30 09:00:00") }

  before do
    stub_const("Clock", Class.new)
    allow(reader).to receive(:call)
  end

  it "creates a running run before reading and returns conflict without changing an existing running run" do
    running_run = HistorySyncRun.create!(
      status: "running",
      started_at: Time.zone.parse("2026-04-30 08:55:00"),
      running_lock_key: described_class::RUNNING_LOCK_KEY
    )

    result = service.call

    expect(result).to be_conflict
    expect(result.running_run).to eq(running_run)
    expect(reader).not_to have_received(:call)
    expect(running_run.reload).to have_attributes(
      status: "running",
      started_at: Time.zone.parse("2026-04-30 08:55:00"),
      processed_count: 0,
      saved_count: 0,
      running_lock_key: described_class::RUNNING_LOCK_KEY
    )
  end

  it "converts a root failure into a failed run and does not mutate sessions" do
    indexed_at = Time.zone.parse("2026-04-29 09:00:00")
    existing = create_session(
      session_id: "existing-session",
      source_fingerprint: fingerprint_for("existing"),
      indexed_at: indexed_at
    )
    failure = CopilotHistory::Types::ReadFailure.new(
      code: "root_missing",
      path: "/tmp/missing-history",
      message: "history root does not exist"
    )
    allow(reader).to receive(:call).and_return(CopilotHistory::Types::ReadResult::Failure.new(failure:))

    result = service.call

    expect(result).to be_failed
    expect(result.code).to eq("root_missing")
    expect(result.message).to eq("history root does not exist")
    expect(result.details).to eq(path: "/tmp/missing-history")
    expect(result.sync_run).to have_attributes(
      status: "failed",
      finished_at: now,
      failed_count: 1,
      failure_summary: "history root does not exist",
      running_lock_key: nil
    )
    expect(existing.reload).to have_attributes(
      source_fingerprint: fingerprint_for("existing"),
      indexed_at: indexed_at,
      conversation_preview: "existing existing-session"
    )
  end

  it "inserts new sessions and records succeeded counts" do
    session = build_session(session_id: "new-session", issues: [])
    fingerprint = fingerprint_for("new")
    attributes = attributes_for(session, fingerprint)
    allow(reader).to receive(:call).and_return(success_result(session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(record_builder).to receive(:call).with(session:, indexed_at: now, source_fingerprint: fingerprint).and_return(attributes)

    result = service.call

    expect(result).to be_succeeded
    expect(CopilotSession.find_by!(session_id: "new-session")).to have_attributes(
      source_fingerprint: fingerprint,
      indexed_at: now
    )
    expect(result.sync_run).to have_attributes(
      status: "succeeded",
      processed_count: 1,
      inserted_count: 1,
      updated_count: 0,
      saved_count: 1,
      skipped_count: 0,
      degraded_count: 0,
      running_lock_key: nil
    )
  end

  it "updates changed sessions, skips matching sessions, and does not rewrite skipped payloads" do
    changed = build_session(session_id: "changed-session")
    skipped = build_session(session_id: "skipped-session")
    old_indexed_at = Time.zone.parse("2026-04-29 09:00:00")
    old_fingerprint = fingerprint_for("old")
    changed_fingerprint = fingerprint_for("changed")
    skipped_fingerprint = fingerprint_for("same")
    create_session(session_id: "changed-session", source_fingerprint: old_fingerprint, indexed_at: old_indexed_at)
    create_session(session_id: "skipped-session", source_fingerprint: skipped_fingerprint, indexed_at: old_indexed_at)
    allow(reader).to receive(:call).and_return(success_result(changed, skipped))
    allow(fingerprint_builder).to receive(:call).with(source_paths: changed.source_paths).and_return(changed_fingerprint)
    allow(fingerprint_builder).to receive(:call).with(source_paths: skipped.source_paths).and_return(skipped_fingerprint)
    allow(record_builder).to receive(:call)
      .with(session: changed, indexed_at: now, source_fingerprint: changed_fingerprint)
      .and_return(attributes_for(changed, changed_fingerprint, conversation_preview: "updated"))

    result = service.call

    expect(result).to be_succeeded
    expect(CopilotSession.find_by!(session_id: "changed-session")).to have_attributes(
      source_fingerprint: changed_fingerprint,
      indexed_at: now,
      conversation_preview: "updated"
    )
    expect(CopilotSession.find_by!(session_id: "skipped-session")).to have_attributes(
      source_fingerprint: skipped_fingerprint,
      indexed_at: old_indexed_at,
      conversation_preview: "existing skipped-session"
    )
    expect(record_builder).not_to have_received(:call).with(
      session: skipped,
      indexed_at: anything,
      source_fingerprint: anything
    )
    expect(result.sync_run).to have_attributes(
      processed_count: 2,
      inserted_count: 0,
      updated_count: 1,
      saved_count: 1,
      skipped_count: 1
    )
  end

  it "updates matching-fingerprint sessions when the search projection version is stale" do
    session = build_session(session_id: "stale-search-text-session")
    old_indexed_at = Time.zone.parse("2026-04-29 09:00:00")
    fingerprint = fingerprint_for("same")
    create_session(
      session_id: "stale-search-text-session",
      source_fingerprint: fingerprint,
      indexed_at: old_indexed_at,
      search_text: "old noisy projection",
      search_text_version: 1
    )
    allow(reader).to receive(:call).and_return(success_result(session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(record_builder).to receive(:call)
      .with(session:, indexed_at: now, source_fingerprint: fingerprint)
      .and_return(attributes_for(session, fingerprint, conversation_preview: "updated projection", search_text: "updated projection text"))

    result = service.call

    expect(result).to be_succeeded
    expect(CopilotSession.find_by!(session_id: "stale-search-text-session")).to have_attributes(
      source_fingerprint: fingerprint,
      indexed_at: now,
      conversation_preview: "updated projection",
      search_text: "updated projection text",
      search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION
    )
    expect(result.sync_run).to have_attributes(
      updated_count: 1,
      saved_count: 1,
      skipped_count: 0
    )
  end

  it "does not modify raw source files or delete sessions missing from the latest read result" do
    Tempfile.create([ "history-sync-service", ".jsonl" ]) do |raw_file|
      raw_file.write("raw event payload\n")
      raw_file.flush
      raw_file_path = Pathname.new(raw_file.path)
      raw_contents = File.binread(raw_file_path)
      session = build_session(
        session_id: "raw-preserved-session",
        source_paths: { events: raw_file_path }
      )
      stale_session = create_session(
        session_id: "stale-read-model-session",
        source_fingerprint: fingerprint_for("stale"),
        indexed_at: Time.zone.parse("2026-04-29 09:00:00")
      )
      fingerprint = fingerprint_for("raw-preserved")
      allow(reader).to receive(:call).and_return(success_result(session))
      allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
      allow(record_builder).to receive(:call)
        .with(session:, indexed_at: now, source_fingerprint: fingerprint)
        .and_return(attributes_for(session, fingerprint))

      result = service.call

      expect(result).to be_succeeded
      expect(File).to exist(raw_file_path)
      expect(File.binread(raw_file_path)).to eq(raw_contents)
      expect(CopilotSession.exists?(id: stale_session.id)).to be(true)
    end
  end

  it "persists degraded sessions and completes with issues" do
    issue = CopilotHistory::Types::ReadIssue.new(
      code: CopilotHistory::Errors::ReadErrorCode::EVENT_PARTIAL_MAPPING,
      message: "event payload matched partially",
      source_path: "/tmp/events.jsonl",
      sequence: 1,
      severity: :warning
    )
    session = build_session(session_id: "degraded-session", source_state: :degraded, issues: [ issue ])
    fingerprint = fingerprint_for("degraded")
    allow(reader).to receive(:call).and_return(success_result(session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(record_builder).to receive(:call)
      .with(session:, indexed_at: now, source_fingerprint: fingerprint)
      .and_return(attributes_for(session, fingerprint, source_state: "degraded", degraded: true, issue_count: 1))

    result = service.call

    expect(result).to be_succeeded
    expect(result.sync_run).to have_attributes(
      status: "completed_with_issues",
      processed_count: 1,
      degraded_count: 1,
      degradation_summary: "1 sessions degraded"
    )
    expect(CopilotSession.find_by!(session_id: "degraded-session")).to have_attributes(
      source_state: "degraded",
      degraded: true,
      issue_count: 1
    )
  end

  it "counts sessions with degraded source state as degraded even when issue details are empty" do
    session = build_session(session_id: "state-degraded-session", source_state: :degraded, issues: [])
    fingerprint = fingerprint_for("state-degraded")
    allow(reader).to receive(:call).and_return(success_result(session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(record_builder).to receive(:call)
      .with(session:, indexed_at: now, source_fingerprint: fingerprint)
      .and_return(attributes_for(session, fingerprint, source_state: "degraded", degraded: true))

    result = service.call

    expect(result).to be_succeeded
    expect(result.sync_run).to have_attributes(
      status: "completed_with_issues",
      processed_count: 1,
      degraded_count: 1,
      degradation_summary: "1 sessions degraded"
    )
    expect(CopilotSession.find_by!(session_id: "state-degraded-session")).to have_attributes(
      source_state: "degraded",
      degraded: true
    )
  end

  it "rolls back session mutations on persistence failure and releases the running lock" do
    session = build_session(session_id: "rollback-session")
    invalid_session = build_session(session_id: "invalid-session")
    fingerprint = fingerprint_for("rollback")
    invalid_fingerprint = fingerprint_for("invalid")
    allow(reader).to receive(:call).and_return(success_result(session, invalid_session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(fingerprint_builder).to receive(:call).with(source_paths: invalid_session.source_paths).and_return(invalid_fingerprint)
    allow(record_builder).to receive(:call)
      .with(session:, indexed_at: now, source_fingerprint: fingerprint)
      .and_return(attributes_for(session, fingerprint))
    allow(record_builder).to receive(:call)
      .with(session: invalid_session, indexed_at: now, source_fingerprint: invalid_fingerprint)
      .and_return(attributes_for(invalid_session, invalid_fingerprint).merge(session_id: nil))

    result = service.call

    expect(result).to be_failed
    expect(result.code).to eq("history_sync_failed")
    expect(result.details.fetch(:failure_class)).to eq("ActiveRecord::RecordInvalid")
    expect(CopilotSession.where(session_id: "rollback-session")).not_to exist
    expect(CopilotSession.where(session_id: "invalid-session")).not_to exist
    expect(result.sync_run).to have_attributes(
      status: "failed",
      finished_at: now,
      failed_count: 1,
      running_lock_key: nil
    )
  end

  it "handles session uniqueness errors as persistence failures and releases the running lock" do
    session = build_session(session_id: "duplicate-session")
    fingerprint = fingerprint_for("duplicate")
    allow(reader).to receive(:call).and_return(success_result(session))
    allow(fingerprint_builder).to receive(:call).with(source_paths: session.source_paths).and_return(fingerprint)
    allow(record_builder).to receive(:call)
      .with(session:, indexed_at: now, source_fingerprint: fingerprint)
      .and_return(attributes_for(session, fingerprint))
    allow(CopilotSession).to receive(:find_by).with(session_id: "duplicate-session").and_return(nil)
    allow(CopilotSession).to receive(:create!).and_raise(ActiveRecord::RecordNotUnique)

    result = service.call

    expect(result).to be_failed
    expect(result.code).to eq("history_sync_failed")
    expect(result.details.fetch(:failure_class)).to eq("ActiveRecord::RecordNotUnique")
    expect(result.sync_run).to have_attributes(
      status: "failed",
      failed_count: 1,
      running_lock_key: nil
    )
  end

  def success_result(*sessions)
    CopilotHistory::Types::ReadResult::Success.new(root: nil, sessions: sessions)
  end

  def build_session(
    session_id:,
    source_state: :complete,
    issues: [],
    source_paths: { events: Pathname.new("/tmp/#{session_id}/events.jsonl") }
  )
    CopilotHistory::Types::NormalizedSession.new(
      session_id:,
      source_format: :current,
      source_state:,
      created_at: "2026-04-29T00:00:00Z",
      updated_at: "2026-04-29T00:05:00Z",
      events: [],
      message_snapshots: [],
      issues:,
      source_paths:
    )
  end

  def fingerprint_for(label)
    {
      "complete" => true,
      "artifacts" => {
        "events" => {
          "path" => "/tmp/#{label}/events.jsonl",
          "mtime" => "2026-04-30T00:00:00Z",
          "size" => label.length,
          "status" => "ok"
        }
      }
    }
  end

  def create_session(
    session_id:,
    source_fingerprint:,
    indexed_at:,
    search_text: "search text #{session_id}",
    search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION
  )
    CopilotSession.create!(
      attributes_for(
        build_session(session_id:),
        source_fingerprint,
        indexed_at:,
        conversation_preview: "existing #{session_id}",
        search_text:,
        search_text_version:
      )
    )
  end

  def attributes_for(
    session,
    source_fingerprint,
    indexed_at: now,
    conversation_preview: "preview #{session.session_id}",
    search_text: "search text #{session.session_id}",
    source_state: session.source_state.to_s,
    degraded: session.issues.any?,
    issue_count: session.issues.length,
    search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION
  )
    {
      session_id: session.session_id,
      source_format: session.source_format.to_s,
      source_state: source_state,
      created_at_source: session.created_at,
      updated_at_source: session.updated_at,
      event_count: 0,
      message_snapshot_count: 0,
      issue_count: issue_count,
      degraded: degraded,
      conversation_preview: conversation_preview,
      search_text: search_text,
      search_text_version: search_text_version,
      message_count: 0,
      activity_count: 0,
      source_paths: { "events" => session.source_paths.fetch(:events).to_s },
      source_fingerprint: source_fingerprint,
      summary_payload: { id: session.session_id },
      detail_payload: { id: session.session_id },
      indexed_at: indexed_at
    }
  end
end

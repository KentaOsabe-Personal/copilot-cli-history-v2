require "rails_helper"

RSpec.describe CopilotSession do
  def valid_attributes
    {
      session_id: "session-1",
      source_format: "current",
      source_state: "complete",
      created_at_source: nil,
      updated_at_source: nil,
      cwd: "/work/app",
      git_root: "/work/app",
      repository: "example/repo",
      branch: "main",
      selected_model: "gpt-5",
      event_count: 2,
      message_snapshot_count: 1,
      issue_count: 0,
      degraded: false,
      conversation_preview: "hello",
      search_text: "hello gpt-5",
      search_text_version: CopilotHistory::Persistence::SessionSearchTextBuilder::VERSION,
      message_count: 1,
      activity_count: 1,
      source_paths: { "events" => "/tmp/events.jsonl" },
      source_fingerprint: { "complete" => true, "artifacts" => {} },
      summary_payload: { "id" => "session-1" },
      detail_payload: { "id" => "session-1", "conversation" => [] },
      indexed_at: Time.zone.parse("2026-04-30 03:00:00")
    }
  end

  it "accepts a complete read model with missing history source dates" do
    session = described_class.new(valid_attributes)

    expect(session).to be_valid
    expect(session.created_at_source).to be_nil
    expect(session.updated_at_source).to be_nil
  end

  it "requires the natural key, format, state, payloads, source metadata, and indexed timestamp" do
    required_fields = %i[
      session_id
      source_format
      source_state
      source_paths
      source_fingerprint
      summary_payload
      detail_payload
      search_text
      search_text_version
      indexed_at
    ]

    required_fields.each do |field|
      session = described_class.new(valid_attributes.merge(field => nil))

      expect(session).not_to be_valid
      expect(session.errors[field]).to be_present
    end
  end

  it "allows only canonical source formats and states" do
    invalid = described_class.new(valid_attributes.merge(source_format: "future", source_state: "partial"))

    expect(invalid).not_to be_valid
    expect(invalid.errors[:source_format]).to be_present
    expect(invalid.errors[:source_state]).to be_present
  end

  it "requires count fields to be non-negative integers" do
    count_fields = %i[event_count message_snapshot_count issue_count message_count activity_count]

    count_fields.each do |field|
      session = described_class.new(valid_attributes.merge(field => -1))

      expect(session).not_to be_valid
      expect(session.errors[field]).to be_present
    end
  end

  it "requires JSON contract fields to be objects" do
    json_fields = %i[source_paths source_fingerprint summary_payload detail_payload]

    json_fields.each do |field|
      session = described_class.new(valid_attributes.merge(field => [ "not", "an", "object" ]))

      expect(session).not_to be_valid
      expect(session.errors[field]).to be_present
    end
  end

  it "prevents duplicate session IDs" do
    described_class.create!(valid_attributes)

    duplicate = described_class.new(valid_attributes.merge(source_format: "legacy"))

    expect(duplicate).not_to be_valid
    expect(duplicate.errors[:session_id]).to be_present
  end

  it "stores issue and degradation state distinctly from valid payloads" do
    session = described_class.new(valid_attributes.merge(degraded: true, issue_count: 2))

    expect(session).to be_valid
    expect(session.degraded).to be(true)
    expect(session.issue_count).to eq(2)
  end

  it "allows an empty search text but rejects a missing search text" do
    empty_search_text = described_class.new(valid_attributes.merge(search_text: ""))
    missing_search_text = described_class.new(valid_attributes.merge(search_text: nil))

    expect(empty_search_text).to be_valid
    expect(missing_search_text).not_to be_valid
    expect(missing_search_text.errors[:search_text]).to be_present
  end

  it "requires a non-negative integer search text version" do
    missing_version = described_class.new(valid_attributes.merge(search_text_version: nil))
    negative_version = described_class.new(valid_attributes.merge(search_text_version: -1))

    expect(missing_version).not_to be_valid
    expect(missing_version.errors[:search_text_version]).to be_present
    expect(negative_version).not_to be_valid
    expect(negative_version.errors[:search_text_version]).to be_present
  end
end

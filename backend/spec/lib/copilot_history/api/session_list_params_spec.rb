require "rails_helper"

RSpec.describe CopilotHistory::Api::SessionListParams do
  subject(:parser) { described_class.new }

  let(:now) { Time.zone.parse("2026-05-03T12:00:00Z") }

  describe "#call" do
    it "normalizes date-only from and to as an inclusive day range" do
      result = parser.call(
        params: {
          "from" => "2026-04-01",
          "to" => "2026-04-30"
        },
        now: now
      )

      expect(result).to be_a(described_class::Result)
      expect(result.from_time).to eq(Time.zone.parse("2026-04-01T00:00:00Z"))
      expect(result.to_time).to eq(Time.zone.local(2026, 4, 30).end_of_day)
      expect(result.limit).to be_nil
    end

    it "normalizes datetime from and to without changing one-sided boundaries" do
      result = parser.call(
        params: {
          from: "2026-04-01T09:30:00+09:00",
          to: "2026-04-30T18:45:00+09:00"
        },
        now: now
      )

      expect(result).to be_a(described_class::Result)
      expect(result.from_time).to eq(Time.zone.parse("2026-04-01T00:30:00Z"))
      expect(result.to_time).to eq(Time.zone.parse("2026-04-30T09:45:00Z"))
    end

    it "does not mix a default upper bound when only from is specified" do
      result = parser.call(params: { from: "2026-04-20" }, now: now)

      expect(result.from_time).to eq(Time.zone.parse("2026-04-20T00:00:00Z"))
      expect(result.to_time).to be_nil
    end

    it "does not mix a default lower bound when only to is specified" do
      result = parser.call(params: { to: "2026-04-20" }, now: now)

      expect(result.from_time).to be_nil
      expect(result.to_time).to eq(Time.zone.local(2026, 4, 20).end_of_day)
    end

    it "uses the last 30 days when neither from nor to is specified" do
      result = parser.call(params: {}, now: now)

      expect(result.from_time).to eq(now - 30.days)
      expect(result.to_time).to eq(now)
    end

    it "accepts a positive integer limit" do
      result = parser.call(params: { limit: "25" }, now: now)

      expect(result.limit).to eq(25)
    end

    it "normalizes search text by trimming and collapsing whitespace" do
      result = parser.call(params: { search: "  apply   patch\nfailure  " }, now: now)

      expect(result).to be_a(described_class::Result)
      expect(result.search_term).to eq("apply patch failure")
    end

    it "treats blank search text as omitted" do
      result = parser.call(params: { search: " \t\n " }, now: now)

      expect(result).to be_a(described_class::Result)
      expect(result.search_term).to be_nil
    end

    it "keeps search text together with date range and limit criteria" do
      result = parser.call(
        params: {
          from: "2026-04-01",
          to: "2026-04-30",
          limit: "25",
          search: "gpt-5"
        },
        now: now
      )

      expect(result.from_time).to eq(Time.zone.parse("2026-04-01T00:00:00Z"))
      expect(result.to_time).to eq(Time.zone.local(2026, 4, 30).end_of_day)
      expect(result.limit).to eq(25)
      expect(result.search_term).to eq("gpt-5")
    end

    it "treats an omitted limit as unlimited" do
      result = parser.call(params: { from: "2026-04-01" }, now: now)

      expect(result.limit).to be_nil
    end

    it "returns a client error for an invalid from date" do
      result = parser.call(params: { from: "not-a-date" }, now: now)

      expect(result).to be_invalid_query(field: "from", reason: "invalid_datetime")
    end

    it "returns a client error for an invalid to date" do
      result = parser.call(params: { to: "2026-02-30" }, now: now)

      expect(result).to be_invalid_query(field: "to", reason: "invalid_datetime")
    end

    it "returns a client error when from is after to" do
      result = parser.call(
        params: {
          from: "2026-05-01",
          to: "2026-04-01"
        },
        now: now
      )

      expect(result).to be_invalid_query(field: "range", reason: "from_after_to")
    end

    it "returns a client error for a non-positive limit" do
      result = parser.call(params: { limit: "0" }, now: now)

      expect(result).to be_invalid_query(field: "limit", reason: "positive_integer_required")
    end

    it "returns a client error for a non-integer limit" do
      result = parser.call(params: { limit: "1.5" }, now: now)

      expect(result).to be_invalid_query(field: "limit", reason: "positive_integer_required")
    end

    it "returns a client error for search text over the maximum length" do
      result = parser.call(params: { search: "a" * 201 }, now: now)

      expect(result).to be_invalid_query(field: "search", reason: "too_long")
    end

    it "returns a client error for search text containing display-hostile control characters" do
      result = parser.call(params: { search: "hello\u0000world" }, now: now)

      expect(result).to be_invalid_query(field: "search", reason: "control_character")
    end
  end

  matcher :be_invalid_query do |field:, reason:|
    match do |actual|
      expect(actual).to be_a(CopilotHistory::Api::Types::SessionIndexResult::Invalid)
      expect(actual.code).to eq("invalid_session_list_query")
      expect(actual.message).to eq("session list query is invalid")
      expect(actual.details).to include(field:, reason:)
    end
  end
end

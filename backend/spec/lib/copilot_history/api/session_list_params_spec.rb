require "rails_helper"

RSpec.describe CopilotHistory::Api::SessionListParams do
  subject(:parser) { described_class.new }

  let(:now) { Time.zone.parse("2026-05-03T12:00:00Z") }

  describe "#call" do
    # 概要・目的: 「normalizes date-only from and to as an inclusive day range」を通じて、正規化・projection・presenter
    #   の変換契約を検証する。
    # テストケース: 「normalizes date-only from and to as an inclusive day range」の条件・入力・操作を実行する。
    # 期待値: date-only from and to as an inclusive day range が正規化されること。
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

    # 概要・目的: 「normalizes datetime from and to without changing one-sided
    #   boundaries」を通じて、正規化・projection・presenter の変換契約を検証する。
    # テストケース: 「normalizes datetime from and to without changing one-sided boundaries」の条件・入力・操作を実行する。
    # 期待値: datetime from and to without changing one-sided boundaries が正規化されること。
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

    # 概要・目的: 「does not mix a default upper bound when only from is specified」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「does not mix a default upper bound when only from is specified」の条件・入力・操作を実行する。
    # 期待値: mix a default upper bound when only from is specified しないこと。
    it "does not mix a default upper bound when only from is specified" do
      result = parser.call(params: { from: "2026-04-20" }, now: now)

      expect(result.from_time).to eq(Time.zone.parse("2026-04-20T00:00:00Z"))
      expect(result.to_time).to be_nil
    end

    # 概要・目的: 「does not mix a default lower bound when only to is specified」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「does not mix a default lower bound when only to is specified」の条件・入力・操作を実行する。
    # 期待値: mix a default lower bound when only to is specified しないこと。
    it "does not mix a default lower bound when only to is specified" do
      result = parser.call(params: { to: "2026-04-20" }, now: now)

      expect(result.from_time).to be_nil
      expect(result.to_time).to eq(Time.zone.local(2026, 4, 20).end_of_day)
    end

    # 概要・目的: 「uses the last 30 days when neither from nor to is specified」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「uses the last 30 days when neither from nor to is specified」の条件・入力・操作を実行する。
    # 期待値: the last 30 days when neither from nor to is specified が使われること。
    it "uses the last 30 days when neither from nor to is specified" do
      result = parser.call(params: {}, now: now)

      expect(result.from_time).to eq(now - 30.days)
      expect(result.to_time).to eq(now)
    end

    # 概要・目的: 「accepts a positive integer limit」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「accepts a positive integer limit」の条件・入力・操作を実行する。
    # 期待値: a positive integer limit が受け入れられること。
    it "accepts a positive integer limit" do
      result = parser.call(params: { limit: "25" }, now: now)

      expect(result.limit).to eq(25)
    end

    # 概要・目的: 「normalizes search text by trimming and collapsing whitespace」を通じて、正規化・projection・presenter
    #   の変換契約を検証する。
    # テストケース: 「normalizes search text by trimming and collapsing whitespace」の条件・入力・操作を実行する。
    # 期待値: search text by trimming and collapsing whitespace が正規化されること。
    it "normalizes search text by trimming and collapsing whitespace" do
      result = parser.call(params: { search: "  apply   patch\nfailure  " }, now: now)

      expect(result).to be_a(described_class::Result)
      expect(result.search_term).to eq("apply patch failure")
    end

    # 概要・目的: 「treats blank search text as omitted」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「treats blank search text as omitted」の条件・入力・操作を実行する。
    # 期待値: blank search text が omitted として扱われること。
    it "treats blank search text as omitted" do
      result = parser.call(params: { search: " \t\n " }, now: now)

      expect(result).to be_a(described_class::Result)
      expect(result.search_term).to be_nil
    end

    # 概要・目的: 「keeps search text together with date range and limit criteria」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「keeps search text together with date range and limit criteria」の条件・入力・操作を実行する。
    # 期待値: search text together with date range が維持され、limit criteriaこと。
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

    # 概要・目的: 「treats an omitted limit as unlimited」を通じて、検索・日付条件と query 組み立てを検証する。
    # テストケース: 「treats an omitted limit as unlimited」の条件・入力・操作を実行する。
    # 期待値: an omitted limit が unlimited として扱われること。
    it "treats an omitted limit as unlimited" do
      result = parser.call(params: { from: "2026-04-01" }, now: now)

      expect(result.limit).to be_nil
    end

    # 概要・目的: 「returns a client error for an invalid from date」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「returns a client error for an invalid from date」の条件・入力・操作を実行する。
    # 期待値: a client error for an invalid from date を返すこと。
    it "returns a client error for an invalid from date" do
      result = parser.call(params: { from: "not-a-date" }, now: now)

      expect(result).to be_invalid_query(field: "from", reason: "invalid_datetime")
    end

    # 概要・目的: 「returns a client error for an invalid to date」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「returns a client error for an invalid to date」の条件・入力・操作を実行する。
    # 期待値: a client error for an invalid to date を返すこと。
    it "returns a client error for an invalid to date" do
      result = parser.call(params: { to: "2026-02-30" }, now: now)

      expect(result).to be_invalid_query(field: "to", reason: "invalid_datetime")
    end

    # 概要・目的: 「returns a client error when from is after to」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「returns a client error when from is after to」の条件・入力・操作を実行する。
    # 期待値: a client error when from is after to を返すこと。
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

    # 概要・目的: 「returns a client error for a non-positive limit」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「returns a client error for a non-positive limit」の条件・入力・操作を実行する。
    # 期待値: a client error for a non-positive limit を返すこと。
    it "returns a client error for a non-positive limit" do
      result = parser.call(params: { limit: "0" }, now: now)

      expect(result).to be_invalid_query(field: "limit", reason: "positive_integer_required")
    end

    # 概要・目的: 「returns a client error for a non-integer limit」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「returns a client error for a non-integer limit」の条件・入力・操作を実行する。
    # 期待値: a client error for a non-integer limit を返すこと。
    it "returns a client error for a non-integer limit" do
      result = parser.call(params: { limit: "1.5" }, now: now)

      expect(result).to be_invalid_query(field: "limit", reason: "positive_integer_required")
    end

    # 概要・目的: 「returns a client error for search text over the maximum length」を通じて、HTTP レスポンスとエラー契約を検証する。
    # テストケース: 「returns a client error for search text over the maximum length」の条件・入力・操作を実行する。
    # 期待値: a client error for search text over the maximum length を返すこと。
    it "returns a client error for search text over the maximum length" do
      result = parser.call(params: { search: "a" * 201 }, now: now)

      expect(result).to be_invalid_query(field: "search", reason: "too_long")
    end

    # 概要・目的: 「returns a client error for search text containing display-hostile control characters」を通じて、HTTP
    #   レスポンスとエラー契約を検証する。
    # テストケース: 「returns a client error for search text containing display-hostile control
    #   characters」の条件・入力・操作を実行する。
    # 期待値: a client error for search text containing display-hostile control characters を返すこと。
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

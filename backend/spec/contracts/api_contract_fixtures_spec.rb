require "rails_helper"

RSpec.describe "API contract fixtures" do
  let(:fixture_root) do
    [
      Rails.root.join("..", ".kiro", "specs", "api-contract-fixtures", "fixtures").expand_path,
      Pathname.new("/workspace/.kiro/specs/api-contract-fixtures/fixtures")
    ].find(&:exist?)
  end
  let(:manifest_path) { fixture_root.join("manifest.json") }
  let(:spec_root) { fixture_root.parent }
  let(:requirements_path) { spec_root.join("requirements.md") }
  let(:contract_path) { spec_root.join("contract.md") }
  let(:manifest) { parse_json(manifest_path) }
  let(:scenarios) { manifest.fetch("scenarios") }

  def parse_json(path)
    JSON.parse(path.read)
  end

  def fixture_path(relative_path)
    fixture_root.join(relative_path)
  end

  def response_for(scenario)
    parse_json(fixture_path(scenario.fetch("response")))
  end

  def request_for(scenario)
    parse_json(fixture_path(scenario.fetch("request")))
  end

  def expect_common_request_shape(request, scenario)
    expect(request).to include(
      "method" => scenario.fetch("method"),
      "path" => a_string_matching(%r{\A/api/}),
      "query" => a_kind_of(Hash),
      "body" => nil
    )
  end

  def expect_error_envelope(body)
    expect(body).to include("error")
    expect(body.fetch("error")).to include(
      "code" => a_kind_of(String),
      "message" => a_kind_of(String),
      "details" => a_kind_of(Hash)
    )
  end

  def requirement_ids
    current_requirement = nil

    requirements_path.read.lines.filter_map do |line|
      if (match = line.match(/\A### Requirement (\d+):/))
        current_requirement = match[1]
        next
      end

      next unless current_requirement

      match = line.match(/\A(\d+)\. /)
      "#{current_requirement}.#{match[1]}" if match
    end
  end

  # 概要・目的: manifest が全 scenario の request / response fixture を壊れていない JSON として参照できる契約を検証する。
  # テストケース: manifest の scenario metadata、fixture path、request shape、response status を横断的に読み込む。
  # 期待値: 全参照 path が存在し、JSON parse に成功し、request method と response status が manifest と一致すること。
  it "loads every manifest scenario with matching request and response fixtures" do
    expect(manifest).to include("version" => 1)
    expect(scenarios).not_to be_empty

    scenarios.each do |scenario|
      request_path = fixture_path(scenario.fetch("request"))
      response_path = fixture_path(scenario.fetch("response"))

      expect(request_path).to exist
      expect(response_path).to exist

      request = request_for(scenario)
      response = response_for(scenario)

      expect(scenario).to include(
        "id" => a_kind_of(String),
        "method" => a_string_matching(/\A(GET|POST)\z/),
        "endpoint" => a_string_matching(%r{\A/api/}),
        "status" => a_kind_of(Integer),
        "payload_kind" => a_string_matching(/\A(success|error)\z/),
        "requirements" => all(a_string_matching(/\A\d+\.\d+\z/)),
        "frontend_types" => all(a_kind_of(String))
      )
      expect_common_request_shape(request, scenario)
      expect(response.fetch("status")).to eq(scenario.fetch("status"))
    end
  end

  # 概要・目的: success response fixture が endpoint 種別ごとの代表 top-level shape を維持する契約を検証する。
  # テストケース: list、detail、history sync の success scenario を manifest から抽出して response body を確認する。
  # 期待値: list は data 配列と meta、detail は data object、sync は sync_run と counts を持つこと。
  it "validates success response top-level shapes by endpoint kind" do
    success_scenarios = scenarios.select { |scenario| scenario.fetch("payload_kind") == "success" }

    expect(success_scenarios).not_to be_empty

    success_scenarios.each do |scenario|
      body = response_for(scenario).fetch("body")

      case scenario.fetch("id")
      when /\Asessions\.index\./
        expect(body.fetch("data")).to be_a(Array)
        expect(body.fetch("meta")).to include(
          "count" => a_kind_of(Integer),
          "partial_results" => satisfy { |value| value == true || value == false }
        )
      when /\Asessions\.show\./
        expect(body.fetch("data")).to include(
          "id" => a_kind_of(String),
          "raw_included" => satisfy { |value| value == true || value == false }
        )

        if scenario.fetch("id") == "sessions.show.detail_success"
          expect(body.fetch("data")).to include(
            "source_format" => a_kind_of(String),
            "conversation" => a_kind_of(Hash),
            "activity" => a_kind_of(Hash),
            "timeline" => a_kind_of(Array)
          )
        end
      when /\Ahistory_sync\./
        data = body.fetch("data")

        expect(data.fetch("sync_run")).to include(
          "id" => a_kind_of(Integer),
          "status" => a_kind_of(String),
          "started_at" => a_kind_of(String)
        )
        expect(data.fetch("counts")).to include(
          "processed_count" => a_kind_of(Integer),
          "saved_count" => a_kind_of(Integer),
          "degraded_count" => a_kind_of(Integer)
        )
      else
        raise "Unhandled success scenario #{scenario.fetch("id")}"
      end
    end
  end

  # 概要・目的: error response fixture が frontend normalization の前提となる common error envelope を維持する契約を検証する。
  # テストケース: manifest の error scenario を抽出し、HTTP status と error.code / message / details を確認する。
  # 期待値: 全 error fixture が 4xx / 5xx status と top-level error envelope を持つこと。
  it "validates common error envelopes" do
    error_scenarios = scenarios.select { |scenario| scenario.fetch("payload_kind") == "error" }

    expect(error_scenarios).not_to be_empty

    error_scenarios.each do |scenario|
      response = response_for(scenario)

      expect(response.fetch("status")).to be_between(400, 599)
      expect_error_envelope(response.fetch("body"))
    end
  end

  # 概要・目的: 全 acceptance criteria ID が fixture set 内で追跡可能な契約を検証する。
  # テストケース: requirements.md から numeric ID を抽出し、manifest または contract note の coverage 記録と照合する。
  # 期待値: 全 requirement ID が fixture scenario か contract note のいずれかに対応付けられていること。
  it "maps every requirement id to manifest scenarios or contract notes" do
    manifest_requirement_ids = scenarios.flat_map { |scenario| scenario.fetch("requirements") }
    contract_requirement_ids = contract_path.read.scan(/\b\d+\.\d+\b/)
    covered_requirement_ids = (manifest_requirement_ids + contract_requirement_ids).uniq

    expect(covered_requirement_ids).to include(*requirement_ids)
  end
end

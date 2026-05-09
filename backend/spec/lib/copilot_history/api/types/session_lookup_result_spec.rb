require "rails_helper"

RSpec.describe CopilotHistory::Api::Types::SessionLookupResult do
  describe "public states" do
    # 概要・目的: 「only exposes found and not found states for detail lookup」を通じて、正規化・projection・presenter
    #   の変換契約を検証する。
    # テストケース: 「only exposes found and not found states for detail lookup」の条件・入力・操作を実行する。
    # 期待値: 「only exposes found and not found states for detail lookup」で示す状態または振る舞いが成立すること。
    it "only exposes found and not found states for detail lookup" do
      expect(described_class.constants(false)).to contain_exactly(:Found, :NotFound)
    end
  end

  describe described_class::Found do
    # 概要・目的: 「carries the stored detail payload without raw reader state」を通じて、DB 保存・validation・一意性制約を検証する。
    # テストケース: 「carries the stored detail payload without raw reader state」の条件・入力・操作を実行する。
    # 期待値: the stored detail payload without raw reader state が保持されて渡されること。
    it "carries the stored detail payload without raw reader state" do
      detail_payload = {
        id: "session-123",
        source_format: "current",
        timeline: [],
        raw_included: false
      }

      result = described_class.new(detail_payload:)

      expect(described_class.members).to eq([ :detail_payload ])
      expect(result.detail_payload).to eq(detail_payload)
      expect(result).not_to respond_to(:root)
      expect(result).not_to respond_to(:session)
    end

    # 概要・目的: 「exposes legacy presenter state only when explicitly provided」を通じて、reader と fixture
    #   の読取・劣化時の扱いを検証する。
    # テストケース: 「exposes legacy presenter state only when explicitly provided」の条件・入力・操作を実行する。
    # 期待値: legacy presenter state only when explicitly provided が公開されること。
    it "exposes legacy presenter state only when explicitly provided" do
      session = instance_double("NormalizedSession")
      result = described_class.new(root: nil, session:)

      expect(result).to respond_to(:root)
      expect(result).to respond_to(:session)
      expect(result.root).to be_nil
      expect(result.session).to eq(session)
    end
  end

  describe described_class::NotFound do
    # 概要・目的: 「retains only the requested session id in the public miss envelope」を通じて、正規化・projection・presenter
    #   の変換契約を検証する。
    # テストケース: 「retains only the requested session id in the public miss envelope」の条件・入力・操作を実行する。
    # 期待値: 「retains only the requested session id in the public miss envelope」で示す状態または振る舞いが成立すること。
    it "retains only the requested session id in the public miss envelope" do
      result = described_class.new(session_id: "session-123")

      expect(described_class.members).to eq([ :session_id ])
      expect(result.session_id).to eq("session-123")
    end
  end
end

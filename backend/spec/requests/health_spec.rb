require "rails_helper"

RSpec.describe "Health", type: :request do
  # 概要・目的: 「returns ok」を通じて、ヘルスチェックエンドポイントの正常応答を検証する。
  # テストケース: 「returns ok」の条件・入力・操作を実行する。
  # 期待値: GET /up が HTTP 200 OK を返すこと。
  it "returns ok" do
    host! "localhost"
    get "/up"

    expect(response).to have_http_status(:ok)
  end
end

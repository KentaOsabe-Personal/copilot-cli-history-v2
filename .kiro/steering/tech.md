# 技術スタック

updated_at: 2026-05-09

## アーキテクチャ

このリポジトリは、**frontend / backend / MySQL を Docker Compose で束ねるモノレポ**です。  
フロントエンドは React ベースの SPA、バックエンドは Rails API、データ永続化は MySQL という責務分離を基本にします。  
Copilot CLI の raw files は同期時に読み取り、通常の一覧・詳細 API は MySQL 上の read model を参照します。

## コア技術

- **Frontend**: React 19 / React Router 7 / TypeScript 6 / Vite / Vitest / Tailwind CSS 4
- **Backend**: Ruby 4 / Rails 8.1 API mode / RSpec
- **Database**: MySQL 9.7
- **Runtime / Dev Env**: Docker Compose をローカル開発の正本とする

## 主要ライブラリと役割

- **Vite**: フロントエンドの高速な開発サーバーとビルド
- **Vitest + Testing Library**: UI の振る舞いをテストで確認する
- **React Router**: 一覧と詳細を SPA 内で切り替える read-only 導線を保つ
- **Tailwind CSS**: 画面試作と UI 実装を素早く進める
- **RSpec Rails**: バックエンドの API / lib / request spec を支える
- **Rack CORS**: SPA と Rails API の分離を保ったままローカル接続を許可する
- **RuboCop / bundler-audit / Brakeman**: Ruby 側のスタイル・依存関係・セキュリティを継続確認する
- **ActiveRecord models**: `CopilotSession` と `HistorySyncRun` を read model と同期履歴の永続化境界として使う
- **Search projection**: `CopilotSession.search_text` と `search_text_version` で会話・preview・issue 由来の検索用テキストを保持する

## 開発標準

### 型安全性

- フロントエンドは TypeScript を前提にし、`noUnusedLocals` や `noUnusedParameters` などの厳しめ設定を使う
- バックエンドは Rails の規約とテストで整合性を支えつつ、暗黙の契約を増やしすぎない

### コード品質

- フロントエンドは ESLint ベースで保守する
- バックエンドは `rubocop-rails-omakase` を基準にする
- Ruby 側は `bin/ci` に lint / dependency audit / static analysis を集約する

### テスト

- フロントエンドは `pnpm test` で Vitest を実行する
- フロントエンドの検証は component / hook / presentation utility を小さく分けて行う
- バックエンドは `bundle exec rspec` を使い、`spec/requests` や `spec/lib` を軸に確認する
- DB schema / model の振る舞いは `spec/db` と `spec/models` に切り出し、reader / presenter の unit spec と分ける
- ローカル実行は Docker Compose 経由を標準にし、環境差分を減らす

## 開発環境

### 必須ツール

- Docker / Docker Compose
- Node.js 系ツールはコンテナ内の pnpm を前提に扱う
- Ruby / Bundler もコンテナ内実行を基本にする
- Copilot CLI 履歴は backend コンテナへ read-only mount して扱う

### 共通コマンド

```bash
# 開発環境起動
docker compose up --build

# フロントエンド lint / build / test
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm lint"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm build"

# フロントエンドテスト
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"

# バックエンド品質確認
docker compose run --rm backend bin/ci

# バックエンドテスト
docker compose run --rm -e RAILS_ENV=test backend bundle exec rspec
```

## 重要な技術判断

### 1. Docker Compose を開発の正本にする

ルートの `docker-compose.yml` と各 Dockerfile を基準に、サービス間接続・ポート・依存関係を揃えます。  
ローカルに個別セットアップ手順を増やすより、まず Compose で再現できる状態を優先します。

### 2. Rails は API 専用で使う

`config.api_only = true` を有効にし、バックエンドは UI を持たない JSON API として整理します。  
表示責務は React 側に寄せ、バックエンドは読取・正規化・提供に集中させます。

### 3. フロントエンドは軽量な SPA 基盤を保つ

Vite + React + TypeScript を中心に、初期段階では過度な抽象化や巨大な状態管理を持ち込みません。  
履歴一覧や詳細表示に必要な UI を、小さな部品から積み上げます。

### 4. 品質確認は既存ツールに寄せる

新しい独自フローを増やすより、frontend は ESLint / Vitest、backend は RSpec / RuboCop / Brakeman / bundler-audit を活用します。  
既存コマンドに乗ることを優先し、判断基準を散らさないようにします。

### 5. current / legacy を共通 contract に正規化する

履歴 reader は保存形式ごとの差を読み取り層で吸収し、API から見える shape は共通化します。  
UI や controller で format 分岐を増やすより、`copilot_history` 配下の query / presenter / types に寄せます。

### 6. read model は再生成可能な補助層として扱う

`copilot_sessions` は raw files から作り直せる summary / detail payload を保持し、API の表示速度と絞り込みを支えます。  
raw files を一次ソースから外さず、payload builder と fingerprint 比較で insert / update / skip を判断します。

### 7. 同期は同期的な API 操作として扱う

`POST /api/history/sync` は初期実装では background job に逃がさず、同期中 lock と `HistorySyncRun` の状態で競合・失敗・部分劣化を表します。  
Solid Queue など Rails 標準の非同期基盤は存在しても、履歴同期の正本フローとしてはまだ使わない前提です。

### 8. session list は DB query と明示 params で絞る

`GET /api/sessions` は DB の source timestamp を基準に並べ、`from` / `to` / `limit` を request params として受け取ります。  
主要な frontend は初期表示と空条件リセットで JST 基準の直近 7 日 range を明示送信し、再読込や同期後 refresh でも同じ query contract を維持します。backend の no-query fallback は互換性のため直近 30 日を保ちます。

### 9. session search は read model の projection で扱う

`GET /api/sessions` の `search` param は `search_text` に対する DB query として扱い、raw files を都度検索しません。  
検索対象の作り方は `SessionSearchTextBuilder::VERSION` と `search_text_version` で管理し、projection の意味が変わるときは migration / sync 側で再生成できる状態を保ちます。

### 10. root failure と partial degradation を分けて返す

履歴ルートが読めないときは共通 error envelope で失敗を返し、個別セッションの破損は degraded と issue 一覧に閉じ込めます。  
「全部失敗」か「一部だけ壊れているか」を API 契約で区別するのが前提です。

### 11. API 接続先は明示設定に限定する

frontend は `VITE_API_BASE_URL` を必須の絶対 URL として扱います。  
暗黙の相対パスに頼らず、SPA と Rails API の接続先を環境変数で明示する前提です。

---
_依存関係の一覧ではなく、開発判断に効く技術上の前提と標準を残す_

# プロジェクト構造

updated_at: 2026-05-09

## 組織方針

このリポジトリは、**サービス単位で責務を分けたモノレポ**として扱います。  
ルートでは開発環境・共有ドキュメント・Kiro の project memory を管理し、実装コードは `frontend/` と `backend/` の内側で完結させるのが基本です。

## ディレクトリパターン

### Frontend アプリ
**Location**: `/frontend/`  
**Purpose**: React SPA の画面・UI テスト・ビルド設定を置く  
**Example**: `src/main.tsx` がエントリーポイント、`src/app/AppShell.tsx` が共通レイアウト、`tests/test/setup.ts` が Vitest 共通設定

### Frontend test tree
**Location**: `/frontend/tests/`  
**Purpose**: frontend のテストコードとテスト用データを production code から分離し、`src/` と対応する階層で置く  
**Example**: `src/features/sessions/components/SessionSummaryCard.tsx` に対するテストは `tests/features/sessions/components/SessionSummaryCard.test.tsx`、テスト用データは `tests/features/sessions/testing/sessionUiTestData.ts` に置く

### Frontend feature slice
**Location**: `/frontend/src/features/`  
**Purpose**: 機能ごとに API / hooks / components / pages / presentation を近接配置する  
**Example**: `features/sessions/` 配下で `api/sessionApi.ts`, `hooks/useSessionDetail.ts`, `pages/SessionDetailPage.tsx`, `presentation/sessionIndexCriteria.ts` を同じ文脈にまとめる

### Backend API
**Location**: `/backend/`  
**Purpose**: Rails API、読取ロジック、永続化、API 提供を担う  
**Example**: `app/controllers/api` は薄い HTTP 入口に保ち、`config/` に環境設定、`spec/` に request/lib/support 系のテストを配置する

### Backend read models
**Location**: `/backend/app/models/`, `/backend/db/migrate/`  
**Purpose**: API 表示用 read model と同期履歴を ActiveRecord の境界として保持する  
**Example**: `CopilotSession` は summary/detail payload、source fingerprint、検索 projection、`HistorySyncRun` は同期状態・件数・失敗概要を持つ

### Backend domain namespace
**Location**: `/backend/lib/copilot_history/`  
**Purpose**: Copilot 履歴の読取・正規化・API 向け整形を Rails 本体から分離して置く  
**Example**: `api/session_index_query.rb`, `api/presenters/session_detail_presenter.rb`, `projections/activity_projector.rb`, `types/normalized_session.rb`

### Backend persistence / sync namespace
**Location**: `/backend/lib/copilot_history/persistence/`, `/backend/lib/copilot_history/sync/`  
**Purpose**: raw reader の normalized session を DB payload に変換し、明示同期 API から insert / update / skip を実行する  
**Example**: `SessionRecordBuilder`, `SourceFingerprintBuilder`, `SessionSearchTextBuilder` で保存属性を作り、`HistorySyncService` が `HistorySyncRun` と `CopilotSession` を更新する

### Database bootstrap
**Location**: `/mysql/`  
**Purpose**: MySQL コンテナの初期化に必要なファイルだけを置く  
**Example**: `mysql/init/` を compose から read-only mount して初期投入に使う

### Project memory
**Location**: `/.kiro/steering/`, `/.kiro/specs/`  
**Purpose**: プロジェクト全体の判断基準と、機能ごとの仕様を分けて保持する  
**Example**: steering は横断ルール、specs は個別機能の要件・設計・タスク

## 命名規約

- **Frontend files**: React コンポーネントは `App.tsx` のような PascalCase、テストは `*.test.tsx`
- **Frontend feature hooks**: hook は `useSessionIndex.ts` のように `use` 接頭辞で置く
- **Backend files**: Rails 規約に従い、controller は `*_controller.rb`、spec は `*_spec.rb`
- **Ruby constants**: クラス・モジュールは PascalCase
- **Backend service objects**: query / presenter / reader は役割が分かる接尾辞で切る
- **Docs / configs**: 既存ファイル名に合わせ、ルートの運用ドキュメントは用途が分かる名前を優先する

## import / load の整理

```ts
import './index.css'
import App from './App.tsx'
```

```rb
module CopilotHistory
  module Api
    class SessionIndexQuery
    end
  end
end
```

**Frontend**:
- 現状は `src/` 内の相対 import を基本にする
- パスエイリアスはまだ導入していないため、必要になるまでは増やさない
- feature 内では API / hook / presentation utility を相対 import で閉じ、横断依存を増やしすぎない

**Backend**:
- Rails の autoload と規約配置を基本にする
- `lib/` 配下は `config.autoload_lib` で読み込む前提に寄せ、手動 require を増やしすぎない
- API 向けの orchestration は `CopilotHistory::Api` 名前空間に集め、controller に整形ロジックを溜めない
- 永続化変換は `CopilotHistory::Persistence`、同期 orchestration は `CopilotHistory::Sync` に分け、query / presenter / reader と混ぜない

## コード構成の原則

### 1. ルートは統合、各サービス配下は独立

Compose、Dockerfile、README、Kiro 関連はルートで管理します。  
一方で、アプリ実装は frontend / backend の責務境界をまたいで混在させません。

### 2. バックエンドは Rails 規約を優先

新しい reader や domain logic を追加するときも、まず Rails 標準の置き場所を検討します。  
共通処理は `lib/` や `concerns/` を使い、無秩序なトップレベル追加を避けます。

### 3. HTTP と履歴ドメインを分離する

request routing と response status は controller が担い、履歴の読取・検索・整形は `lib/copilot_history` に寄せます。  
`query -> presenter -> types` の流れを保ち、UI 向け schema の都合を reader 層へ逆流させません。

### 4. DB read model と raw reader の境界を分ける

raw files の探索・正規化は reader / projections / types に閉じ、DB 保存用の shape は persistence namespace で作ります。  
session API の query は `CopilotSession` を参照し、raw reader へ直接戻らない構成を基本にします。

### 5. 同期 UI は sessions feature の中に閉じる

履歴同期ボタン、同期状態表示、空状態からの同期導線は `frontend/src/features/sessions/` に置きます。  
`useHistorySync` は API 呼び出しと一覧再読込を束ねますが、個別コンポーネントには同期結果の表示責務だけを渡します。

### 6. 一覧条件は presentation utility と hook で共有する

日付範囲や検索語の正規化、validation、query key 生成は sessions feature の `presentation/` に置きます。  
`useSessionIndex` は range と search term をまとめた criteria を API query に変換し、ページやフォームは条件入力と表示に集中させます。

### 7. フロントエンドは production と tests を対応させる

フロントエンドの production code は `frontend/src/`、テストコードは `frontend/tests/` に分けます。  
テスト側は `src/` の階層に対応させ、component / hook / page / presentation utility の粒度が分かる場所に `*.test.ts` / `*.test.tsx` を置きます。グローバルなテスト初期化は `tests/test/` に切り出します。

### 8. 新しい知識は steering か specs に寄せる

リポジトリ全体に効くルールは `steering` に、機能固有の詳細は `specs` に置きます。  
新しいコードが既存パターンに従うなら、steering を毎回増やす必要はありません。

---
_ファイル一覧ではなく、どこに何を置くべきかという判断パターンを残す_

# プロジェクト構造

updated_at: 2026-06-13

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

### Django project
**Location**: `/backend/backend_config/`  
**Purpose**: Django settings / URL routing / ASGI / WSGI の project 境界を置く  
**Example**: `settings.py` で installed apps、repository backend、CORS origin、SQLite default を定義し、`urls.py` で health と history API を束ねる

### Backend health app
**Location**: `/backend/health/`  
**Purpose**: runtime の最小起動確認を BigQuery や raw files から独立して提供する  
**Example**: `GET /up` は `{"status":"ok"}` を返し、settings import と routing の smoke test に使う

### Backend history API app
**Location**: `/backend/history_api/`  
**Purpose**: sync / list / detail の HTTP 境界、query validation、dependency selection、response helpers を置く  
**Example**: `views.py` は repository と service を呼び、`services.py` が同期 orchestration、`query_validation.py` が request params の正規化を担う

### Copilot history domain
**Location**: `/backend/copilot_history/`  
**Purpose**: Copilot raw files の探索、current / legacy reader、event normalization、API payload projection を Django app から分離して置く  
**Example**: `catalog_reader.py`, `current_reader.py`, `legacy_reader.py`, `event_normalizer.py`, `api/response_projection.py` で raw source から contract payload への流れを作る

### BigQuery read model
**Location**: `/backend/history_read_model/`  
**Purpose**: BigQuery schema、DDL、repository、fake repository、metadata comparison、management command をまとめる  
**Example**: `bigquery_schema.py` が table contract、`bigquery_repository.py` が query / upsert、`management/commands/init_bigquery_read_model.py` が dry-run / execute / compare を提供する

### Backend tests
**Location**: `/backend/tests/`  
**Purpose**: Python / Django のテストを production package と分離し、責務別に置く  
**Example**: `tests/copilot_history/` は reader / presenter、`tests/history_api/` は HTTP / service、`tests/history_read_model/` は BigQuery schema / repository contract を確認する

### Project memory
**Location**: `/.kiro/steering/`, `/.kiro/specs/`  
**Purpose**: プロジェクト全体の判断基準と、機能ごとの仕様を分けて保持する  
**Example**: steering は横断ルール、specs は個別機能の要件・設計・タスク

## 命名規約

- **Frontend files**: React コンポーネントは `SessionList.tsx` のような PascalCase、テストは `*.test.tsx`
- **Frontend feature hooks**: hook は `useSessionIndex.ts` のように `use` 接頭辞で置く
- **Frontend presentation utilities**: UI から独立した整形・条件生成は `presentation/` に置き、camelCase の関数名にする
- **Backend Python modules**: snake_case file と typed function / dataclass を基本にする
- **Django apps**: HTTP 境界は app 単位で分け、domain reader や read model repository と混ぜない
- **Backend tests**: `test_*.py` を責務別ディレクトリへ置き、fixture / fake はテスト側に閉じる
- **Docs / configs**: 既存ファイル名に合わせ、ルートの運用ドキュメントは用途が分かる名前を優先する

## import / load の整理

```ts
import './index.css'
import App from './App.tsx'
```

```python
from history_read_model.repository import SessionRepository
from copilot_history.api.response_projection import build_session_detail_payload
```

**Frontend**:
- 現状は `src/` 内の相対 import を基本にする
- パスエイリアスはまだ導入していないため、必要になるまでは増やさない
- feature 内では API / hook / presentation utility を相対 import で閉じ、横断依存を増やしすぎない

**Backend**:
- Python package と Django app の import を標準にし、sys.path 操作や手動 loader を増やさない
- `history_api` は HTTP / orchestration、`copilot_history` は raw reader / projection、`history_read_model` は persistence access に分ける
- BigQuery 実接続と fake repository は同じ repository contract に寄せ、view や frontend に datastore 差分を漏らさない
- Django settings import と health endpoint は BigQuery credentials や raw files に依存させない

## コード構成の原則

### 1. ルートは統合、各サービス配下は独立

Compose、Dockerfile、README、Kiro 関連はルートで管理します。  
一方で、アプリ実装は frontend / backend の責務境界をまたいで混在させません。

### 2. Backend は Django / Python 側を正とする

新しい backend 実装は `backend_config`、`health`、`history_api`、`copilot_history`、`history_read_model` のいずれかに置きます。  
Rails / MySQL 由来の runtime artifact は削除済みです。`app/`、`config/`、`db/migrate/`、`lib/copilot_history/*.rb`、`spec/` は現行設計の追加先にしません。

### 3. HTTP と履歴ドメインを分離する

request routing と response status は Django view / URL が担い、履歴の読取・検索・整形は `copilot_history` と `history_read_model` に寄せます。  
`reader -> projection -> repository -> API response` の境界を保ち、UI 向け schema の都合を raw reader 層へ逆流させません。

### 4. BigQuery read model と raw reader の境界を分ける

raw files の探索・正規化は `copilot_history` に閉じ、BigQuery 保存用の row / SQL / MERGE は `history_read_model` に置きます。  
session API の query は repository contract を参照し、通常表示から raw reader へ直接戻らない構成を基本にします。

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

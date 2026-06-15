# 技術スタック

updated_at: 2026-06-13

## アーキテクチャ

このリポジトリは、**React frontend と Django backend を Docker Compose で束ねるモノレポ**です。  
フロントエンドは read-only な履歴閲覧 SPA、バックエンドは Copilot CLI の raw files を同期し、BigQuery read model から session API を返す Django API として扱います。

Copilot CLI の raw files は一次ソースです。BigQuery は再生成可能な read model / index であり、通常の一覧・詳細 API は BigQuery 上の `copilot_sessions` を参照します。同期 API は raw files を読み取り、staging table と MERGE を使って read model を更新します。

## コア技術

- **Frontend**: React 19 / React Router 7 / TypeScript 6 / Vite / Vitest / Tailwind CSS 4
- **Backend**: Python 3.14 / Django 5.2 / pytest / ruff / mypy
- **Read model**: BigQuery dataset + tables (`copilot_sessions`, `session_write_stage`, `history_sync_runs`)
- **Runtime / Dev Env**: Docker Compose をローカル開発の正本とする

## 主要ライブラリと役割

- **Vite**: フロントエンドの開発サーバーとビルドを担う
- **Vitest + Testing Library**: UI component / hook / presentation utility の振る舞いを検証する
- **React Router**: セッション一覧と詳細の read-only 導線を SPA 内で切り替える
- **Tailwind CSS**: UI 実装のスタイル基盤として使う
- **Django**: health endpoint、history API、management command の HTTP / runtime 境界を担う
- **pytest + pytest-django**: backend の unit / API / contract tests を支える
- **ruff / mypy / django-stubs**: Python 側の lint、import 整理、strict typing を継続確認する
- **google-cloud-bigquery**: BigQuery read model の query、DDL dry-run / execute、staging + MERGE を扱う
- **Fake repository**: BigQuery 実接続なしで API contract と orchestration を検証する

## 開発標準

### 型安全性

- フロントエンドは TypeScript を前提にし、`noUnusedLocals` や `noUnusedParameters` などの厳しめ設定を使う
- バックエンドは Python 3.14 と mypy strict を前提にし、Django 境界にも型を付ける
- JSON payload は presenter / repository row の境界で shape を固定し、view で ad hoc に組み替えない

### コード品質

- フロントエンドは ESLint / TypeScript / Vitest に寄せる
- バックエンドは `ruff check .`、`mypy .`、`python -m pytest` を標準ゲートにする
- BigQuery 実接続が必要な確認は opt-in とし、通常の unit / API tests は fake repository で実行できる状態を保つ

### テスト

- フロントエンドは `pnpm test` で Vitest を実行する
- フロントエンドの検証は component / hook / page / presentation utility を小さく分ける
- バックエンドは `python -m pytest` を使い、`tests/copilot_history`、`tests/history_api`、`tests/history_read_model` を責務別に分ける
- API contract fixture と Django response shape の一致を、実装境界をまたいで確認する
- テストを追加・更新するときは、各 `it` / test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを残す

## 開発環境

### 必須ツール

- Docker / Docker Compose
- Node.js / pnpm は frontend コンテナ内実行を基本にする
- Python / Django tooling は backend コンテナ内実行を基本にする
- Copilot CLI 履歴は backend コンテナへ read-only mount して扱う
- BigQuery 実接続を使う場合は ADC または `GOOGLE_APPLICATION_CREDENTIALS` を明示する

### 共通コマンド

```bash
# 開発環境起動
docker compose up --build

# フロントエンド lint / build / test
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm lint"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm build"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"

# バックエンド品質確認
docker compose run --rm backend bin/quality

# バックエンド個別確認
docker compose run --rm backend bin/lint
docker compose run --rm backend bin/typecheck
docker compose run --rm backend bin/test

# BigQuery schema の dry-run
docker compose run --rm backend python manage.py init_bigquery_read_model
```

## 重要な技術判断

### 1. Docker Compose を開発の正本にする

ルートの `docker-compose.yml` と Dockerfile を基準に、frontend / backend の port、mount、環境変数を揃えます。  
ホスト OS の個別セットアップに依存するより、Compose で再現できる状態を優先します。

### 2. Backend の active runtime は Django とする

新しい API、reader、repository、management command は Python / Django 側へ追加します。  
Rails / MySQL 由来の runtime artifact は削除済みで、現行の実装判断では active runtime として扱いません。

### 3. BigQuery は read model として扱う

BigQuery は raw files から再生成できる補助層です。  
通常 DB のような OLTP 更新や Django ORM migration の対象にせず、schema contract、DDL helper、repository、staging + MERGE の境界で扱います。

### 4. current / legacy を共通 contract に正規化する

履歴 reader は保存形式ごとの差を読み取り層で吸収し、API から見える shape は presenter / response projection で共通化します。  
UI や Django view で format 分岐を増やさず、`copilot_history` 配下に正規化責務を閉じます。

### 5. 同期は明示 API 操作として扱う

`POST /api/history/sync` は raw files を読み、read model を更新する利用者操作です。  
初期方針として file watch や background job に逃がさず、sync run の status / counts / failure summary で結果を追えるようにします。

### 6. session list は read model query と明示 params で絞る

`GET /api/sessions` は source timestamp 由来の partition date、検索語、limit などの明示 params を repository query に変換します。  
raw files を都度検索せず、`search_text` と `search_text_version` を持つ projection を使います。

### 7. root failure と partial degradation を分けて返す

履歴ルートが読めないときは共通 error envelope で失敗を返し、個別セッションの破損は degraded と issue 一覧に閉じ込めます。  
「全部失敗」か「一部だけ壊れているか」を API 契約で区別します。

### 8. API 接続先は明示設定に限定する

frontend は `VITE_API_BASE_URL` を必須の絶対 URL として扱います。  
暗黙の相対パスに頼らず、SPA と Django API の接続先を環境変数で明示します。

---
_依存関係の一覧ではなく、開発判断に効く技術上の前提と標準を残す_

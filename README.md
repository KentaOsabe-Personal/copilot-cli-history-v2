# Copilot CLI Session History

Docker ベースで frontend / backend / MySQL を起動する Phase 1 の開発環境です。

| Service | Stack | Version line | Port |
| --- | --- | --- | --- |
| frontend | React + TypeScript + Vite + Vitest + Tailwind CSS | React 19.2 / TypeScript 6 / Node.js 24 / pnpm | 51730 |
| backend | Rails API + RSpec | Ruby 4 / Rails 8.1 | 30000 |
| db | MySQL | MySQL 9.7 | 33006 |

## 起動

```bash
docker compose up --build
```

- 初回起動では frontend の `pnpm install`、backend の `bundle install`、`bin/rails db:prepare` もあわせて実行されます。
- frontend: http://localhost:51730
- backend: http://localhost:30000
- backend health: http://localhost:30000/up
- frontend の依存は bind mount された `frontend/node_modules` に入るため、ホストの VSCode でも `vite/client` や `vitest/globals` を含む型解決ができます。
- この frontend 構成は個人利用の開発環境を前提としており、`pnpm install` / `pnpm dev` / `pnpm test` / `pnpm build` はコンテナ内だけで実行します。ホスト側では `pnpm` を使った実行を想定していません。
- mysql: `localhost:33006`
- backend はホストの `~/.copilot` を read-only で `/copilot-home` にマウントし、`COPILOT_HOME=/copilot-home` で会話履歴を参照します。
- backend の `/app/tmp` は named volume のため、古い `tmp/pids/server.pid` が見えないまま残ることがあります。起動時に stale PID を削除してから Rails を立ち上げます。

## 使い始めの流れ

1. `docker compose up --build` を実行します。
2. frontend の http://localhost:51730 を開きます。
3. セッション一覧画面で **「履歴を最新化」** を押して、ホストの `~/.copilot` にある履歴を MySQL に取り込みます。
4. 一覧からセッションを開いて詳細を確認します。

- **初回利用時は MySQL が空** なので、最初に手動同期しないと一覧は表示されません。
- 画面の一覧は **直近 7 日** を初期表示にしているため、古い履歴を見たい場合は日付範囲を変更してください。
- Copilot CLI で新しい会話が増えても **自動では同期されません**。最新状態を見たいときは、もう一度 **「履歴を最新化」** を押してください。

## データの流れ

- **一次ソース**: ホストの `~/.copilot` にある Copilot CLI の raw files
- **同期処理**: `POST /api/history/sync` が raw files を読み取り、MySQL の read model に保存
- **通常の表示**: `GET /api/sessions` / `GET /api/sessions/:id` は raw files を毎回読まず、**MySQL から取得**

つまり、このアプリは **「表示はDB参照、raw files の反映は手動同期」** という構成です。  
raw files に履歴が存在していても、同期前は画面に出ません。

## 手動同期の方法

- 画面から: セッション一覧の **「履歴を最新化」** ボタン
- API から:

```bash
curl -X POST http://localhost:30000/api/history/sync
```

同期が成功すると、その時点の raw files の内容が MySQL に保存され、以後の一覧・詳細表示はその保存済みデータを参照します。

## テスト

```bash
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"
docker compose run --rm -e RAILS_ENV=test backend bundle exec rspec
```

## 補足

- ルートの `Dockerfile.frontend` / `Dockerfile.backend` と `docker-compose.yml` を開発環境の正本とします。
- backend は `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_TEST_NAME`, `DB_USERNAME`, `DB_PASSWORD` を使って MySQL に接続します。

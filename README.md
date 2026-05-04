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

- frontend: http://localhost:51730
- backend: http://localhost:30000
- backend health: http://localhost:30000/up
- frontend の依存は bind mount された `frontend/node_modules` に入るため、ホストの VSCode でも `vite/client` や `vitest/globals` を含む型解決ができます。
- mysql: `localhost:33006`
- backend はホストの `~/.copilot` を read-only で `/copilot-home` にマウントし、`COPILOT_HOME=/copilot-home` で会話履歴を参照します。
- backend の `/app/tmp` は named volume のため、古い `tmp/pids/server.pid` が見えないまま残ることがあります。起動時に stale PID を削除してから Rails を立ち上げます。

## テスト

```bash
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"
docker compose run --rm -e RAILS_ENV=test backend bundle exec rspec
```

## 補足

- ルートの `Dockerfile.frontend` / `Dockerfile.backend` と `docker-compose.yml` を開発環境の正本とします。
- backend は `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_TEST_NAME`, `DB_USERNAME`, `DB_PASSWORD` を使って MySQL に接続します。

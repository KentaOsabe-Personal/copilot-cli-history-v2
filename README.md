# Copilot CLI Session History V2

Docker ベースで frontend / backend を起動する開発環境です。現在の active backend runtime は Django backend foundation です。

| Service  | Stack                                             | Version line                                  | Port  |
| -------- | ------------------------------------------------- | --------------------------------------------- | ----- |
| frontend | React + TypeScript + Vite + Vitest + Tailwind CSS | React 19.2 / TypeScript 6 / Node.js 24 / pnpm | 51730 |
| backend  | Django + pytest + ruff + mypy                     | Python 3.14 / Django 5.2                      | 30000 |

## 起動

```bash
docker compose up --build
```

- frontend: http://localhost:51730
- backend: http://localhost:30000
- backend health: http://localhost:30000/up
- frontend の API base URL は `VITE_API_BASE_URL=http://localhost:30000` を維持します。
- frontend の依存は bind mount された `frontend/node_modules` に入るため、ホストの VSCode でも `vite/client` や `vitest/globals` を含む型解決ができます。
- frontend の `pnpm install` / `pnpm dev` / `pnpm test` / `pnpm build` はコンテナ内実行を前提にします。

backend だけを確認する場合は次を使います。

```bash
docker compose up --build backend
curl http://localhost:30000/up
```

`GET /up` の期待 response は最小 JSON です。

```json
{"status":"ok"}
```

## Backend コマンド

```bash
docker compose run --rm backend bin/test
docker compose run --rm backend bin/lint
docker compose run --rm backend bin/typecheck
docker compose run --rm backend bin/quality
```

| Command           | 実行内容                         |
| ----------------- | -------------------------------- |
| `bin/test`      | `python -m pytest`             |
| `bin/lint`      | `ruff check .`                 |
| `bin/typecheck` | `mypy .`                       |
| `bin/quality`   | lint、typecheck、test の順次実行 |

## Frontend コマンド

```bash
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm lint"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm build"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"
```

## データの流れ

- **一次ソース**: ホストの `~/.copilot` にある Copilot CLI の raw files
- **同期処理**: 後続 spec で raw files を読み取り、再生成可能な read model に保存する
- **通常の表示**: 後続 spec で read model から session API を返す

この foundation は raw files を一次ソースとして扱うプロダクト原則を変更しません。

## この foundation で維持するもの

- frontend の接続先は `http://localhost:30000` のままです。
- backend host port は `30000` のままです。
- MySQL は通常 backend の依存ではありません。
- backend は Django project と pytest / lint / type check / quality の入口を提供します。

## この foundation の対象外

- BigQuery schema / 接続
- Copilot raw history reader の Python 移植
- `POST /api/history/sync`
- `GET /api/sessions`
- `GET /api/sessions/:id`
- Django admin / auth / session 機能

後続 spec は `backend/README.md` の追加先と検証入口を確認してから実装します。

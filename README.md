# Copilot CLI Session History V2

Docker ベースで frontend / backend を起動する、Copilot CLI のローカル会話履歴ビューアです。現在の active backend runtime は **Django + BigQuery read model** です。

| Service  | Stack                                             | Version line                                  | Port  |
| -------- | ------------------------------------------------- | --------------------------------------------- | ----- |
| frontend | React + TypeScript + Vite + Vitest + Tailwind CSS | React 19.2 / TypeScript 6 / Node.js 24 / pnpm | 51730 |
| backend  | Django + pytest + ruff + mypy + BigQuery client   | Python 3.14 / Django 5.2                      | 30000 |

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

## API

backend は Django で次の API を提供します。

| Endpoint | 用途 |
| --- | --- |
| `GET /up` | Django runtime の health check |
| `POST /api/history/sync` | Copilot raw files を読み取り、BigQuery read model を明示更新する |
| `GET /api/sessions` | 同期済み read model から session 一覧を返す |
| `GET /api/sessions/<session_id>` | 同期済み read model から session 詳細を返す |

## データの流れ

- **一次ソース**: ホストの `~/.copilot` にある Copilot CLI の raw files
- **同期処理**: `POST /api/history/sync` が raw files を読み取り、再生成可能な BigQuery read model を更新する
- **通常の表示**: `GET /api/sessions` と `GET /api/sessions/<session_id>` が BigQuery read model から JSON API を返す
- **UI 表示**: frontend は明示同期、一覧、日付範囲、検索、cwd tabs、詳細タイムラインを API 契約に沿って表示する

BigQuery は read model / index であり、raw files を一次ソースとするプロダクト原則は変更しません。

## Backend コマンド

```bash
docker compose run --rm backend bin/test
docker compose run --rm backend bin/lint
docker compose run --rm backend bin/typecheck
docker compose run --rm backend bin/quality
```

| Command           | 実行内容                         |
| ----------------- | -------------------------------- |
| `bin/test`        | `python -m pytest`               |
| `bin/lint`        | `ruff check .`                   |
| `bin/typecheck`   | `mypy .`                         |
| `bin/quality`     | lint、typecheck、test の順次実行 |

BigQuery read model の schema SQL 確認は dry-run で実行できます。

```bash
docker compose run --rm backend python manage.py init_bigquery_read_model
```

実際に dataset / table 作成や metadata compare を行う場合は、BigQuery の環境変数と ADC または `GOOGLE_APPLICATION_CREDENTIALS` を設定したうえで実行します。

```bash
docker compose run --rm backend python manage.py init_bigquery_read_model --execute
docker compose run --rm backend python manage.py init_bigquery_read_model --compare
```

## VSCode で backend をデバッグする

VSCode の Run and Debug から `Django backend: attach to Docker` を選ぶと、デバッグ用 Compose override で backend を起動し、`debugpy` に attach します。

使い方:

1. 任意の Python ファイルに breakpoint を置く
2. VSCode の Run and Debug で `Django backend: attach to Docker` を開始する
3. attach 後に http://localhost:30000/up や frontend から API を叩く

デバッグ起動では `docker-compose.debug.yml` により backend command が `python -m debugpy ... -m django runserver ... --noreload` に差し替わります。Django autoreloader は親子プロセスでbreakpointが分かりにくくなるため、debug時は `--noreload` を使います。

## Frontend コマンド

```bash
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm lint"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm build"
docker compose run --rm frontend sh -lc "pnpm install --no-frozen-lockfile && pnpm test"
```

## BigQuery 設定

backend は BigQuery read model を使う場合、次の環境変数を参照します。

| Variable | 用途 |
| --- | --- |
| `HISTORY_API_REPOSITORY_BACKEND` | `bigquery` で BigQuery repository、未指定時は fake repository |
| `BIGQUERY_PROJECT_ID` | BigQuery project |
| `BIGQUERY_DATASET_ID` | read model dataset |
| `BIGQUERY_LOCATION` | dataset / job location |
| `BIGQUERY_TABLE_PREFIX` | 任意の table prefix |
| `BIGQUERY_MAX_BYTES_BILLED_DEFAULT` | query cost guard の任意設定 |
| `BIGQUERY_READ_MODEL_INTEGRATION` | opt-in integration tests / runtime integration の有効化 |
| `GOOGLE_APPLICATION_CREDENTIALS` | service account credentials path。未指定時は ADC を使う |

Compose では `~/.copilot` と `~/.config/gcloud` を backend コンテナへ read-only mount します。

## この runtime で維持するもの

- Copilot raw files は一次ソースです。
- BigQuery read model は再生成可能な補助層です。
- frontend の接続先は `http://localhost:30000` のままです。
- backend host port は `30000` のままです。
- Django admin / auth / session 機能は初期スコープ外で、API は stateless に保ちます。
- Rails / MySQL 由来の runtime artifact は削除済みで、active backend runtime は Django / Python です。

## 補足

リポジトリ全体の判断基準は `.kiro/steering/`、機能ごとの要件・設計・タスクは `.kiro/specs/` に置きます。新しい backend 実装は Django / Python 側へ追加し、テストを追加・更新するときは各 test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを残します。

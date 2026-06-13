# Backend

`backend/` は Django backend の active runtime です。Copilot CLI の raw files を読み取り、BigQuery read model に同期し、frontend が使う history API を提供します。

## Runtime

- Python: `>=3.14,<3.15`
- Django: `>=5.2.8,<5.3`
- Settings module: `backend_config.settings`
- Development database: SQLite default
- Read model: BigQuery (`copilot_sessions`, `session_write_stage`, `history_sync_runs`)
- Health endpoint: `GET /up`
- History API: `POST /api/history/sync`, `GET /api/sessions`, `GET /api/sessions/<session_id>`

Settings import と health check は BigQuery credentials や Copilot raw history files の存在に依存しません。API 実行時の repository backend は `HISTORY_API_REPOSITORY_BACKEND` で切り替えます。

## 起動

ルートディレクトリから実行します。

```bash
docker compose up --build backend
```

backend service は `0.0.0.0:30000` で Django development server を起動します。

```bash
curl http://localhost:30000/up
```

期待する最小 response は次の形です。

```json
{"status":"ok"}
```

## 品質確認

すべてルートディレクトリから Compose 経由で実行できます。

```bash
docker compose run --rm backend bin/test
docker compose run --rm backend bin/lint
docker compose run --rm backend bin/typecheck
docker compose run --rm backend bin/quality
```

各 script の役割は次の通りです。

| Command | 実行内容 | 失敗種別 |
| --- | --- | --- |
| `bin/test` | `python -m pytest` | test failure |
| `bin/lint` | `ruff check .` | lint failure |
| `bin/typecheck` | `mypy .` | type check failure |
| `bin/quality` | lint、typecheck、test の順次実行 | 最初に失敗した確認種別 |

## BigQuery read model

schema SQL の dry-run は credentials なしで確認できます。

```bash
docker compose run --rm backend python manage.py init_bigquery_read_model
```

dataset / table 作成、または既存 metadata との compare は credentials が必要です。

```bash
docker compose run --rm backend python manage.py init_bigquery_read_model --execute
docker compose run --rm backend python manage.py init_bigquery_read_model --compare
```

主な環境変数は次の通りです。

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

## 追加先

- Django project settings / routing: `backend_config/`
- Health endpoint: `health/`
- History API HTTP / orchestration: `history_api/`
- Copilot raw reader / normalizer / presenter: `copilot_history/`
- BigQuery schema / repository / fake repository: `history_read_model/`
- Backend tests: `tests/`
- Tooling configuration: `pyproject.toml`
- Standard commands: `bin/test`, `bin/lint`, `bin/typecheck`, `bin/quality`

テストを追加・更新する場合は、各 `it` / test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを置きます。

## 境界

- Copilot CLI の raw files は一次ソースです。
- BigQuery は再生成可能な read model であり、Django ORM の通常 DB として扱いません。

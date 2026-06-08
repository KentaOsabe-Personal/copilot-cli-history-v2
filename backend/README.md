# Backend

`backend/` は Django backend foundation の active runtime です。後続 spec はこの Django project、`health` app、`tests/`、`bin/*` の検証入口を前提に追加します。

## Runtime

- Python: `>=3.14,<3.15`
- Django: `>=5.2.8,<5.3`
- Settings module: `backend_config.settings`
- Development database: SQLite default
- Health endpoint: `GET /up`

BigQuery、MySQL、Copilot raw history files は settings import や health check の必須条件ではありません。

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

## 追加先

- Django project settings / routing: `backend_config/`
- Health endpoint: `health/`
- Backend tests: `tests/`
- Tooling configuration: `pyproject.toml`
- Standard commands: `bin/test`, `bin/lint`, `bin/typecheck`, `bin/quality`

テストを追加・更新する場合は、各 `it` / test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを置きます。

## 対象外

この foundation spec は次を実装しません。

- BigQuery schema / 接続 / Django database backend 化
- Copilot raw history reader の Python 移植
- `POST /api/history/sync`
- `GET /api/sessions`
- `GET /api/sessions/:id`
- Django admin / auth / session 機能
- Rails / MySQL stack の全面削除

Copilot CLI の raw files は引き続き一次ソースです。DB や検索 index は後続 spec で再生成可能な read model として扱います。

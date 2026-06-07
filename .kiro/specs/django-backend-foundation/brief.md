# Brief: django-backend-foundation

## Problem
開発者は Rails API + MySQL 前提の backend を Django / BigQuery へ移行したいが、まず Django backend が Docker Compose 上で安定して起動し、品質確認とテストを実行できる土台が必要である。土台がないまま reader や API を移植すると、環境差分と実装差分が混ざり、学習とレビューが難しくなる。

## Current State
現行 backend は Rails API mode で、`backend/` 配下に Ruby / Bundler / RSpec / RuboCop / Brakeman / ActiveRecord / MySQL 接続がある。Frontend は `VITE_API_BASE_URL` で backend に接続する。Django project、Python dependency 管理、pytest、ruff、型チェック、Django settings はまだない。

## Desired Outcome
Django 5.2 backend が Python 3.14 runtime で Docker Compose から起動し、`GET /up` が 200 を返す。Python dependency、Django settings、routing、pytest / pytest-django、ruff、型チェックの実行入口が揃い、後続 spec が Python backend にコードを追加できる。

## Approach
`backend/` を Django project として再構成し、現行 frontend から見える API base URL と compose 上の backend service 境界を維持する。BigQuery や履歴 API の実装は後続 spec に譲り、この spec は runtime、settings、health endpoint、品質ツール、テスト基盤に集中する。

## Scope
- **In**: `manage.py`、Django project 設定、Python 3.14 Dockerfile、`pyproject.toml`、health endpoint、pytest / pytest-django、ruff、型チェック設定、基本 README / コマンド更新。
- **Out**: BigQuery schema、BigQuery 接続、履歴 reader 移植、sync / sessions API、Rails / MySQL 削除、frontend 改修。

## Boundary Candidates
- Django project / settings / URL routing
- Python dependency and quality tooling
- Docker Compose backend runtime
- Health check and minimal API smoke test

## Out of Boundary
- Django admin / auth / session の導入
- BigQuery を Django ORM の通常 DB として設定すること
- 既存 Rails reader / API の移植
- Rails backend の削除

## Upstream / Downstream
- **Upstream**: `.kiro/steering/product.md`、`.kiro/steering/tech.md`、`TECH_STACK_MIGRATION_PLAN.md`
- **Downstream**: `bigquery-read-model-schema`、`copilot-history-python-reader`、`django-history-api`

## Existing Spec Touchpoints
- **Extends**: なし。新しい技術基盤 spec として扱う。
- **Adjacent**: `backend-session-api`、`history-sync-api`、`session-api-db-query`

## Constraints
Django 5.2 は LTS 系として採用する。Python 3.14 は stable release として扱うが、依存 package の対応は実装時に確認する。Docker Compose を開発環境の正本とし、frontend の API base URL を不必要に変えない。

# Brief: bigquery-read-model-schema

## Problem
MySQL の `copilot_sessions` / `history_sync_runs` read model を BigQuery に移すには、Django ORM migration とは別に BigQuery 向け schema、dataset 初期化、環境変数、テスト方針を決める必要がある。ここを曖昧にすると後続 repository と API が BigQuery の制約に引きずられて複雑になる。

## Current State
現行 schema は Rails migration と ActiveRecord model に定義され、MySQL に保存されている。移行計画では BigQuery dataset と `copilot_sessions` / `history_sync_runs` table、JSON payload、partition、clustering、staging + MERGE 方針が提案されている。

## Desired Outcome
BigQuery dataset / table schema を作成できる script または management command があり、必要な環境変数とローカル / test の使い分けが文書化されている。BigQuery 実接続なしでも後続 unit test ができるよう、repository fake の前提が定義されている。

## Approach
BigQuery を Django ORM の通常 DB として扱わず、`google-cloud-bigquery` を使う明示的な repository 層の保存先として schema を定義する。schema 初期化は SQL または Python script に寄せ、実接続 integration test は opt-in にする。

## Scope
- **In**: BigQuery dataset / table schema、partition / clustering 方針、schema 初期化 script、環境変数、credentials 手順、fake repository 前提、schema validation test。
- **Out**: sessions query 実装、detail query 実装、staging + MERGE の本実装、Django API、Rails / MySQL 削除。

## Boundary Candidates
- BigQuery schema contract
- Dataset / table initialization
- BigQuery environment and credentials
- Local fake repository and opt-in integration policy

## Out of Boundary
- Django migration で BigQuery schema を管理すること
- Django admin / auth 用 DB の設計
- BigQuery cost 最適化の高度な運用設計

## Upstream / Downstream
- **Upstream**: `django-backend-foundation`、現行 Rails migration、`TECH_STACK_MIGRATION_PLAN.md`
- **Downstream**: `bigquery-session-repository`、`django-history-api`、`react-django-runtime-validation`

## Existing Spec Touchpoints
- **Extends**: なし。MySQL read model spec の後続置換境界として新規 spec にする。
- **Adjacent**: `history-db-read-model`、`history-sync-api`、`session-api-db-query`

## Constraints
raw files は一次ソースで、BigQuery は再生成可能な read model とする。Django ORM 用 BigQuery backend は初期スコープ外。日付 range による partition filter と scan cost 抑制を後続 query の前提として schema に反映する。

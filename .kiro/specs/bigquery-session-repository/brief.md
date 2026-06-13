# Brief: bigquery-session-repository

## Problem
Django API が BigQuery read model を使うには、一覧検索、詳細取得、同期保存を扱う repository が必要である。BigQuery は OLTP 向け DB ではないため、MySQL / ActiveRecord と同じ更新感覚で実装すると cost、性能、DML 制約の問題が起きやすい。

## Current State
現行 backend は ActiveRecord model と DB query で `GET /api/sessions` / `GET /api/sessions/:id` を支え、同期では `CopilotSession` と `HistorySyncRun` を更新している。Python 側では `django-presenters-contract` が生成する summary / detail payload を BigQuery read model に保存する。移行計画では BigQuery repository、query、detail query、staging table + MERGE、`search_text_version` 再生成が提案されている。

## Desired Outcome
Python の BigQuery repository が、session 一覧 query、詳細 query、sync 用 staging load + MERGE upsert、sync run 保存を提供する。日付 range、検索語、limit、session_id 取得が現行 API contract に合う形で扱える。

## Approach
`google-cloud-bigquery` を repository 層で明示的に使い、Django view からは repository interface に依存させる。unit test は fake repository と SQL builder で実行し、実 BigQuery dataset を使う integration test は opt-in にする。

## Scope
- **In**: repository interface、BigQuery client wrapper、sessions list query、session detail query、staging load、MERGE upsert、sync run write、dry run / maximum bytes billed など cost guardrail、fake repository。
- **Out**: Django API endpoint、raw file reader 移植、BigQuery schema 初期化、Rails / Django parity report、Rails / MySQL 削除。

## Boundary Candidates
- Repository interface
- Query builder and parameter validation
- Staging load and MERGE write path
- Fake repository for unit / API tests

## Out of Boundary
- BigQuery を Django ORM として使うこと
- 高度な Search Index / semantic search
- background job 化
- GCP production operation design

## Upstream / Downstream
- **Upstream**: `bigquery-read-model-schema`、`django-presenters-contract`
- **Downstream**: `django-history-api`

## Existing Spec Touchpoints
- **Extends**: なし。MySQL query / persistence の置換境界として新規 spec にする。
- **Adjacent**: `session-api-db-query`、`history-sync-api`、`session-full-text-search`

## Constraints
日付 range を query 条件に入れて scan cost を抑える。同期保存は staging table + MERGE を基本にし、session ごとの細かな update を避ける。BigQuery 実接続なしで主要 test を実行できるよう fake を必ず持つ。

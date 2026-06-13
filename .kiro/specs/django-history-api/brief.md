# Brief: django-history-api

## Problem
Frontend を維持したまま backend を Django / BigQuery に切り替えるには、現行 Rails API と同じ URL、status code、JSON shape を Django で提供する必要がある。API contract が変わると frontend 改修が混ざり、backend 移行の妥当性を検証しにくくなる。

## Current State
現行 Rails API は `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id` を提供し、frontend は `sessionApi.ts` / hooks / pages から利用している。エラー envelope、partial results、degraded issue、日付 range、検索語、詳細 payload が UI に影響する。

## Desired Outcome
Django API が現行 URL と JSON shape で sync / list / detail を返し、frontend の変更なし、または最小変更で接続できる。BigQuery repository fake を使った API tests と、BigQuery repository を使う opt-in integration の入口がある。

## Approach
Django views と URL routing で既存 endpoint を再現し、request validation、repository 呼び出し、presenter payload、error envelope を明示的に分ける。Django REST Framework の採否は design で決めるが、初期 spec では現行 contract 維持を最優先にする。

## Scope
- **In**: `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/<session_id>`、request params validation、CORS、error envelope、repository fake を使う API tests、frontend 接続確認。
- **Out**: reader の新規移植、BigQuery schema 作成、repository の BigQuery 実装、Rails / Django diff report、Rails / MySQL 削除。

## Boundary Candidates
- Django HTTP routing and views
- Request validation and error envelopes
- Repository orchestration
- API tests against contract fixtures

## Out of Boundary
- Frontend UI の作り直し
- 認証 / 認可
- background sync
- Django admin / auth / session

## Upstream / Downstream
- **Upstream**: `bigquery-session-repository`、`django-presenters-contract`、現行 frontend API types
- **Downstream**: なし

## Existing Spec Touchpoints
- **Extends**: なし。Rails API の置換 spec として新規に切る。
- **Adjacent**: `backend-session-api`、`history-sync-api`、`session-api-db-query`、`frontend-history-sync-ui`

## Constraints
現行 frontend から見える JSON shape を維持する。一覧は `{ "data": [...], "meta": { "count": number, "partial_results": boolean } }`、詳細は `{ "data": { ... } }`、エラーは現行 envelope に合わせる。CORS は frontend の開発 URL に合わせる。

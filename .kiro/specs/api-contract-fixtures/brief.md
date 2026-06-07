# Brief: api-contract-fixtures

## Problem
Rails / MySQL から Django / BigQuery へ移行しても、frontend が依存する API request / response shape は維持する必要がある。契約 fixture がないまま移植を始めると、Django 側の差分が仕様変更なのか移植バグなのか判定できない。

## Current State
現行 API contract は Rails request specs、presenter、frontend の `sessionApi.types.ts`、hooks / pages に分散している。主な endpoint は `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id`、`GET /api/sessions/:id?include_raw=true` である。

## Desired Outcome
list / detail / include_raw detail / sync success / sync conflict / validation error / root failure / not found / degraded session の request / response fixture が保存され、後続 Django 実装と parity validation が同じ fixture を参照できる。frontend が依存する shape と status code が明示される。

## Approach
Rails API と frontend 型を基準に、JSON fixture と contract note を作成する。fixture は実装から再生成可能な形にしつつ、spec 生成後は Django presenter / API / parity validation の期待値として使える場所に置く。

## Scope
- **In**: 現行 API endpoint の contract inventory、代表 request / response fixture、status code / error code の一覧、frontend 型との対応表、fixture 更新手順。
- **Out**: Django backend 実装、BigQuery schema、Python reader 移植、frontend UI 改修、Rails / MySQL 削除。

## Boundary Candidates
- API response fixture
- Error envelope and status code contract
- Frontend type mapping
- Contract fixture generation / update workflow

## Out of Boundary
- API shape の変更
- 新規 UI 機能
- BigQuery query 方針
- Django views の実装

## Upstream / Downstream
- **Upstream**: 現行 Rails API、frontend `sessionApi.types.ts`、既存 request specs
- **Downstream**: `copilot-history-python-reader`、`django-presenters-contract`、`django-history-api`、`rails-django-parity-validation`

## Existing Spec Touchpoints
- **Extends**: なし。移行前の contract 固定 spec として新規に切る。
- **Adjacent**: `backend-session-api`、`history-sync-api`、`session-api-db-query`、`frontend-session-ui`、`frontend-history-sync-ui`

## Constraints
fixture と contract note は日本語で記録する。既存 API shape を正本とし、変更が必要な場合は後続 spec で明示的に扱う。テストを追加する場合は各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す。

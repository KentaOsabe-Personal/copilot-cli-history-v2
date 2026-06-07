# Brief: django-presenters-contract

## Problem
Python reader が normalized session を作れても、frontend が利用する summary / detail payload と error envelope が Rails と一致しなければ backend 切替はできない。presenter 互換を Django API や BigQuery repository と混ぜると、表示 contract の差分原因が追いにくい。

## Current State
Rails backend は `SessionIndexPresenter`、`SessionDetailPresenter`、`ErrorPresenter`、`HistorySyncPresenter` で API response を整形している。Frontend は `sessionApi.types.ts` と hooks / pages でその shape に依存している。`api-contract-fixtures` が代表 request / response fixture を固定する。

## Desired Outcome
Python presenter が normalized session と sync result から、Rails fixture と一致する summary payload、detail payload、sync response、error envelope を生成できる。degraded issue、raw inclusion、partial results、not found、validation error、sync conflict の shape が固定される。

## Approach
Python reader / projection の出力を入力にして、HTTP から独立した presenter 関数または class を実装する。`api-contract-fixtures` の期待値と比較する unit / contract test を置き、Django view と BigQuery repository はこの presenter contract に依存する。

## Scope
- **In**: session summary presenter、session detail presenter、sync presenter、error presenter、raw inclusion 表示、partial / degraded issue 表示、fixture 比較 test。
- **Out**: raw file reader 実装、BigQuery query / upsert、Django views、frontend UI 改修、Rails / MySQL 削除。

## Boundary Candidates
- Summary payload presenter
- Detail payload presenter
- Sync response presenter
- Error envelope presenter

## Out of Boundary
- HTTP status 判定の最終 routing
- BigQuery 保存形式の最適化
- raw file parsing
- frontend presentation component

## Upstream / Downstream
- **Upstream**: `api-contract-fixtures`、`copilot-history-python-reader`
- **Downstream**: `bigquery-session-repository`、`django-history-api`、`rails-django-parity-validation`

## Existing Spec Touchpoints
- **Extends**: なし。Rails presenter の Python 移植 spec として新規に切る。
- **Adjacent**: `backend-session-api`、`frontend-session-ui`、`history-sync-api`、`session-api-db-query`

## Constraints
現行 frontend から見える JSON shape を維持する。一覧、詳細、sync、error の fixture を基準に差分を検出する。テストコードには各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す。

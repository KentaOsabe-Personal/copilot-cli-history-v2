# Brief: copilot-history-python-reader

## Problem
Django API が Rails API と互換の session payload を返すには、まず Rails の raw file reader / normalizer / projection の責務を Python に移植する必要がある。reader 移植と BigQuery / HTTP / presenter 実装を同時に進めると、payload 差分の原因が切り分けにくくなる。

## Current State
Rails backend には `backend/lib/copilot_history/` 配下の current / legacy reader、event normalizer、catalog reader、presenter / persistence 系のロジックがある。現行 API は raw files を正規化し、summary / detail payload と degraded issue を扱う。

## Desired Outcome
Python backend の `copilot_history` package で raw files から normalized session を作成できる。current / legacy の差分、root failure、session degraded、conversation / activity projection、search projection の基礎が Python 側で表現される。

## Approach
Rails の reader / normalizer / projection の責務を Python の readers / normalizers / projections / types に分けて移植する。HTTP、BigQuery 保存、API presenter から独立した unit test を整備し、後続 presenter / repository / API が安定した normalized session を利用できるようにする。

## Scope
- **In**: raw file catalog reader、current / legacy reader、event normalizer、typed normalized session、conversation / activity projection、degraded issue、reader / normalizer unit test。
- **Out**: summary / detail API presenter、error envelope、BigQuery query / upsert、Django sync endpoint、frontend 接続、Rails / MySQL 削除、semantic search。

## Boundary Candidates
- Raw source discovery and parsing
- Event normalization
- Conversation / activity projection
- Degradation and root failure representation

## Out of Boundary
- Summary / detail API payload の最終整形
- BigQuery への保存
- HTTP request / response handling
- UI 表示ロジック
- raw file format の仕様変更

## Upstream / Downstream
- **Upstream**: `django-backend-foundation`、`api-contract-fixtures`、現行 Rails `backend/lib/copilot_history/`、既存 fixture
- **Downstream**: `django-presenters-contract`、`bigquery-session-repository`、`django-history-api`、`react-django-runtime-validation`

## Existing Spec Touchpoints
- **Extends**: なし。移植 spec として新規に切る。
- **Adjacent**: `backend-history-reader`、`current-copilot-cli-schema-compatibility`、`history-sync-api`

## Constraints
raw files を正本とし、current / legacy の差分は reader 層で吸収する。API と UI に見える shape を変えない。テストコードには各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す。

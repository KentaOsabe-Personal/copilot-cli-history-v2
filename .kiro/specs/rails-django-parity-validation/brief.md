# Brief: rails-django-parity-validation

## Problem
Django / BigQuery backend を本格切替する前に、Rails / MySQL backend と同じ raw files / fixture で API payload が互換であることを確認する必要がある。差分検証がないと、仕様差と移植バグが混ざったまま Rails / MySQL 削除に進んでしまう。

## Current State
Rails backend は既存 API を提供しており、Django backend は後続 spec で同等 endpoint を提供する予定である。移行計画では別 port で並行稼働し、一覧 / 詳細 payload を比較し、差分を仕様差か不具合かに分類することが求められている。

## Desired Outcome
Rails backend と Django backend を同じ raw files / fixture で並行実行し、sync / list / detail の payload diff report を生成できる。許容差分と修正必須差分が分類され、Rails / MySQL 削除へ進む判断材料が残る。

## Approach
Docker Compose で Rails と Django を一時的に別 port で起動するか、fixture ベースの contract runner で両 API response を取得して比較する。差分は JSON path 単位で記録し、API contract の意図的変更は明示的に承認対象にする。

## Scope
- **In**: 並行稼働設定、payload capture、JSON diff tooling、sync / list / detail の比較、差分分類、validation report、frontend 手動確認手順。
- **Out**: Django API の新規実装、BigQuery repository 実装、Rails / MySQL 削除、frontend 機能追加。

## Boundary Candidates
- Dual backend runtime for validation
- Payload capture and diff
- Contract classification
- Cutover readiness report

## Out of Boundary
- 差分を自動的に仕様変更として許容すること
- 本番運用監視
- Rails / MySQL 削除作業

## Upstream / Downstream
- **Upstream**: `django-history-api`、現行 Rails backend、既存 fixture
- **Downstream**: `remove-rails-mysql-stack`

## Existing Spec Touchpoints
- **Extends**: なし。切替検証 spec として新規に切る。
- **Adjacent**: `backend-session-api`、`history-sync-api`、`session-api-db-query`、`frontend-session-ui`

## Constraints
差分レポートは日本語で残す。raw files は一次ソースとして同一条件で使う。検証は Rails / Django のどちらか一方の都合に寄せず、frontend が依存する contract を基準にする。

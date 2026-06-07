# Brief: remove-rails-mysql-stack

## Problem
Rails / MySQL から Django / BigQuery への切替が検証できた後、古い backend runtime、MySQL service、Ruby tooling、旧 steering / README 記述を残したままにすると、開発者が誤ったコマンドや責務境界を参照し続ける。切替後の正本を明確にする後始末が必要である。

## Current State
ルートには `Dockerfile.backend`、`docker-compose.yml`、`mysql/`、Rails backend、Ruby 品質ツール、MySQL 前提の steering / README がある。Django / BigQuery 移行後はこれらの一部または全部が不要になる。

## Desired Outcome
Rails / MySQL 依存が削除され、Docker Compose、README、`.kiro/steering/tech.md`、`.kiro/steering/structure.md` が Django / BigQuery 前提に更新される。開発・テスト・同期・BigQuery schema 初期化のコマンドが新 stack に揃う。

## Approach
`rails-django-parity-validation` の完了を前提に、旧 runtime / service / docs / commands を段階的に削除または置換する。削除対象と残す対象を明示し、frontend と backend の接続が Django API に向いていることを最終確認する。

## Scope
- **In**: Rails app / Ruby tooling の削除または置換、MySQL service / init files の削除、Docker Compose 更新、README 更新、steering 更新、不要 env vars / scripts の削除、最終 test / smoke check。
- **Out**: Django API の新規実装、BigQuery schema / repository の新規実装、payload parity の初回検証、frontend の大規模再設計。

## Boundary Candidates
- Runtime and dependency removal
- Docker Compose cutover
- Documentation and steering update
- Final smoke and cleanup validation

## Out of Boundary
- parity 未確認のまま Rails / MySQL を削除すること
- API contract の追加変更
- BigQuery production operation hardening

## Upstream / Downstream
- **Upstream**: `rails-django-parity-validation`
- **Downstream**: 将来の Django / BigQuery 前提の機能 spec、検索高度化、運用改善

## Existing Spec Touchpoints
- **Extends**: なし。移行完了後の cleanup spec として新規に切る。
- **Adjacent**: 既存 backend / DB / sync / session API 系 spec 全体

## Constraints
既存 spec は履歴として残し、steering は新しい正本に更新する。Rails / MySQL 削除は parity validation の完了後に限定する。削除作業でもテストコメント規約を守る。

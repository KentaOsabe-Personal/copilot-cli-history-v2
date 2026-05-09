# Roadmap

## Overview

画面表示用のセッション履歴取得を MySQL 上の read model に寄せ、Copilot CLI の raw files 読取を明示的な履歴同期操作へ閉じ込める。raw files は引き続き一次ソースとし、DB は再生成可能な index / read model として扱う。

このロードマップでは、DB 保存基盤、同期 API、既存 session API の DB query 化、frontend の同期導線を段階的に分ける。移行途中でも既存の raw file reader 経由の閲覧体験を維持し、一時的に履歴が見られない期間を作らない。

## Approach Decision

- **Chosen**: 段階的 DB read model 化。まず永続化モデルと同期処理を追加し、同期導線が動いた後に一覧・詳細 API を DB 参照へ切り替える。
- **Why**: 既存の `backend-session-api` と `frontend-session-ui` は read-only の raw reader 表示を前提に承認済みであり、永続化・同期・再読み込み・日付フィルタは明示的に境界外であるため。DB 化を独立 spec に分けることで、既存表示を壊さず検証できる。
- **Rejected alternatives**: 単一 spec で一括実装する案は、migration、sync service、API 契約変更、frontend 操作追加が混在してレビュー境界が大きすぎるため採用しない。既存 session API spec の単純更新だけで扱う案は、永続化と同期 UI が既存 boundary を超えるため採用しない。

## Scope

- **In**: `copilot_sessions` / `history_sync_runs` の DB schema、ActiveRecord model、raw files から DB payload を作る builder、同期 service、`POST /api/history/sync`、session list/detail API の DB query 化、日付 query param、frontend の同期ボタンと空状態表示、backend / frontend tests、README の初回同期説明。
- **Out**: 検索 UI、バックグラウンド job、自動 file watch、削除同期、認証・認可、外部公開向け hardening、raw files を一次ソースから外すこと。

## Constraints

- raw files は一次ソース、MySQL は再生成可能な補助層として扱う。
- Docker Compose を開発環境の正本とする。
- Rails API / React SPA / MySQL の既存責務分離を維持する。
- `GET /api/sessions` と `GET /api/sessions/:id` の DB query 化は、同期 API と frontend 同期導線が完成してから行う。
- 移行途中は既存 raw file reader 経由の閲覧を維持する。
- 初期実装では同期処理を同期的に実行し、バックグラウンド job は導入しない。
- 初期実装では raw files が削除された session を DB から削除しない。

## Boundary Strategy

- **Why this split**: DB read model は schema と保存 contract、sync API は raw reader 実行と upsert、session API DB query は既存表示 API の参照元切替、frontend sync UI は利用者操作に責務を分けられる。依存順に実装すれば、各段階で既存閲覧機能を保持したまま検証できる。
- **Shared seams to watch**: `summary_payload` / `detail_payload` の shape、`source_fingerprint` の比較規則、root failure と session degraded の扱い、DB 空状態と sync error の UI 表示、日付比較に使う `COALESCE(updated_at_source, created_at_source)`。
- **Cutover guardrail**: `session-api-db-query` は frontend の同期導線が完成してから実装・有効化する。先に API を DB only に切り替えると、DB 未投入環境で一覧が空になり、利用者が一時的に履歴を参照できなくなるため。

## Specs (dependency order)

- [ ] history-db-read-model -- Copilot セッション履歴を DB read model として保存する schema / model / payload builder を定義する。Dependencies: none
- [ ] history-sync-api -- raw files を読み取り、DB read model へ同期する service と明示同期 API を追加する。Dependencies: history-db-read-model
- [ ] frontend-history-sync-ui -- frontend に履歴最新化ボタン、DB 空状態、同期中・成功・失敗表示を追加する。Dependencies: history-sync-api
- [ ] session-api-db-query -- 既存 session list/detail API を DB query に切り替え、日付範囲指定を DB 側で処理する。Dependencies: history-db-read-model, history-sync-api, frontend-history-sync-ui

## Follow-up Specs

- [ ] session-date-filtering -- セッション一覧に日付フィルタ UI を追加し、初期表示を直近 1 週間へ絞り、長い履歴表示によるページ全体の横スクロールを抑制する。Dependencies: session-api-db-query, frontend-session-ui, frontend-history-sync-ui
- [ ] session-full-text-search -- セッション一覧に全文検索を追加し、保存済み read model から会話本文・関連メタ情報に一致するセッションを探せるようにする。Dependencies: session-api-db-query, session-date-filtering, history-sync-api

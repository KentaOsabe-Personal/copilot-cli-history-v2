# Brief: session-full-text-search

## Problem

GitHub Copilot CLI のローカル会話履歴を読み返す利用者は、日付範囲だけでは目的のセッションへ素早く辿り着けない。会話本文、エラー文言、ツール呼び出し、issue message などの断片を覚えていても、現状は一覧を開いて preview と詳細を順に確認する必要がある。

## Current State

現在のアプリは、raw files を明示同期で MySQL の `copilot_sessions` read model に保存し、`GET /api/sessions` と `GET /api/sessions/:id` は保存済み read model から返す。frontend にはセッション一覧、日付範囲フィルタ、詳細画面、会話表示、activity / issue 表示、手動同期導線がある。

一方で、検索は既存 roadmap と関連 specs で明示的に対象外だった。日付以外の探索条件はなく、repository / branch / model filter や並び替えもまだ提供されていない。

## Desired Outcome

利用者が一覧画面で検索語を入力し、保存済みセッションの会話本文や関連メタ情報に一致するセッションだけを確認できる。検索は日付範囲と併用でき、結果が空の場合や検索条件を解除した場合も既存の read-only 閲覧体験と整合する。

## Approach

検索用の正規化テキストを read model 側に保持し、`GET /api/sessions` に検索 query param を追加して DB query で絞り込む。初期実装では外部検索エンジンを導入せず、既存の Rails API / MySQL / React UI の責務分離を維持する。

この方針は、raw files を都度読まない既存原則に合い、検索対象の組み立てを同期・保存境界に閉じられる。将来、検索性能やスコアリングが必要になった場合は、同じ検索用テキストを MySQL FULLTEXT index などへ拡張できる。

## Scope

- **In**: 検索対象テキストの保存 contract、既存同期での検索テキスト更新、`GET /api/sessions` の検索 query param、日付範囲と検索語の併用、検索中 / 検索結果 / 検索空状態の frontend 表示、検索条件の解除、backend / frontend tests
- **Out**: 外部検索エンジン、semantic search、ベクトル検索、検索結果スコアリング、検索語ハイライト、repository / branch / model 専用フィルタ、並び替え UI、pagination、詳細画面内検索、履歴の編集・削除・共有、自動同期、認証・認可

## Boundary Candidates

- **Search index construction**: normalized session / saved detail payload から検索対象テキストを作り、read model に保存する
- **Session list query extension**: 既存の日付範囲 query に検索語条件を追加し、既存 response shape を維持する
- **Frontend search control**: 一覧画面で検索語入力、適用、解除、状態表示を行う
- **Empty / error presentation**: 検索結果 0 件、API validation error、通常の空一覧を区別する

## Out of Boundary

- repository / branch / model の構造化フィルタはこの spec では扱わない
- 検索結果のハイライトや relevance ranking はこの spec では必須にしない
- raw files の直接検索や詳細 API での都度検索は行わない
- 共有・エクスポート・マスキングは別 spec として扱う

## Upstream / Downstream

- **Upstream**: `history-db-read-model` の read model 保存境界、`history-sync-api` の同期処理、`session-api-db-query` の DB-backed 一覧 API、`session-date-filtering` の frontend 日付条件管理
- **Downstream**: repository / branch / model フィルタ、検索結果ハイライト、Markdown エクスポート、ブックマーク・タグ、同期差分ビュー

## Existing Spec Touchpoints

- **Extends**: `session-api-db-query` の一覧 query 条件、`history-db-read-model` の保存 payload / schema、`history-sync-api` の保存更新、`session-date-filtering` の一覧条件 UI
- **Adjacent**: `frontend-session-ui` の read-only 閲覧体験、`session-ui-noise-reduction` と `conversation-ui-readability` の表示整理、`frontend-history-sync-ui` の同期後再取得

## Constraints

- raw files は一次ソース、DB read model は再生成可能な補助層として扱う
- 通常表示と検索は保存済み read model を参照し、raw files を検索時に直接読まない
- Rails API / React SPA / MySQL の既存責務分離を維持する
- Docker Compose を開発環境の正本とする
- frontend は `VITE_API_BASE_URL` 経由で Rails API に接続する
- current / legacy の保存形式差分は UI ではなく reader / projection / persistence 側で吸収する
- 既存の read-only viewer 原則を維持し、履歴の編集・削除は追加しない

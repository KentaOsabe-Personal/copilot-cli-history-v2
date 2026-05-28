# Brief: cwd-session-tabs

## Problem
GitHub Copilot CLI のローカル会話履歴を読み返す利用者は、日付範囲や検索語で一覧を絞り込んだ後でも、複数の作業ディレクトリにまたがるセッションを一列の一覧から探す必要がある。

特に同じ期間内に複数プロジェクトで作業している場合、各カードの実行ディレクトリ表示を読み比べながら目的のセッションを探す手間が残っている。

## Current State
セッション一覧 API の `SessionSummary` には `work_context.cwd` が含まれており、DB read model にも `copilot_sessions.cwd` が存在する。現行の一覧 API は取得済みの summary payload を返し、frontend の `useSessionIndex` は日付範囲と検索語を条件に一覧を取得している。

一覧カードでは `buildSessionMetadataItems({ surface: 'summary' })` 経由で実行ディレクトリを表示済みであり、backend の `SessionIndexQuery#search_scope` では互換性のため `search_text` と `cwd` を検索対象にしている。

一方、一覧画面は `SessionList` が API から返された全セッションをそのまま表示しており、作業ディレクトリごとにローカルで表示を切り替える UI はまだ存在しない。

## Desired Outcome
利用者がセッション一覧画面で、現在の API 条件に一致したセッション集合を作業ディレクトリ別タブで切り替えられるようにする。

`すべて` タブでは従来どおり全件を表示し、各 cwd タブでは同じ cwd のセッションだけを既存順で表示する。タブ切り替えはローカル UI state に閉じ、日付範囲、検索語、同期状態、一覧 API の contract を変更しない。

## Approach
取得済みの `state.sessions` を frontend で cwd ごとにグループ化し、`SessionIndexPage` 上で作業ディレクトリ別タブとして表示する。

この方針は既存 API response に含まれる `work_context.cwd` を利用できるため、backend endpoint、DB schema、session list response shape を増やさずに実装できる。日付範囲、検索、同期後 refresh、loading / empty / error 表示の既存 contract も維持しやすい。

比較した代替案として、backend に directory summary endpoint または grouped response を追加する案がある。ただし現状は pagination がなく、タブ表示に必要な情報は既存一覧 response で足りているため、初回実装では変更範囲が大きすぎる。

## Scope
- **In**: frontend のセッション一覧成功表示に作業ディレクトリ別タブを追加する。
- **In**: `SessionSummary[]` から tab model を構築する presentation utility を追加する。
- **In**: `cwd` 正規化、未設定 bucket、件数、表示名、active tab 補正を frontend 側で扱う。
- **In**: `すべて`、cwd 別、`ディレクトリ未設定` の各タブを提供する。
- **In**: 長いパスや重複 basename でも識別できる表示名、`title`、`aria-label` を設計する。
- **In**: タブ選択、左右キー移動、検索結果内でのタブ構築、再取得後の active tab 補正をテストする。
- **In**: 検索 UI とヘッダー説明から「実行ディレクトリも検索対象」という案内を外し、作業ディレクトリは一覧タブで切り替える文脈に寄せる。
- **Out**: backend endpoint、DB schema、一覧 API response shape の追加または変更。
- **Out**: backend の `cwd LIKE` 検索条件の削除。
- **Out**: pagination、server-side aggregation、directory summary API。
- **Out**: repository / branch / model 専用フィルタ、並び替え UI、検索結果スコアリング、検索語ハイライト。

## Boundary Candidates
- `frontend/src/features/sessions/presentation/sessionDirectoryTabs.ts`: セッション配列から tab model を作る純粋関数の境界。
- `frontend/src/features/sessions/components/SessionDirectoryTabs.tsx`: tablist / tab の表示、選択、キーボード操作の境界。
- `frontend/src/features/sessions/pages/SessionIndexPage.tsx`: active tab state と `SessionList` へ渡す表示対象セッションを決める画面統合の境界。
- 検索説明文の更新: backend 挙動を変えず、利用者向け案内だけを今回のタブ UI に合わせる境界。

## Out of Boundary
- 実行ディレクトリ検索を API 契約から完全に外すこと。
- `session-execution-directory-search` の履歴 Spec を書き換えること。
- raw files から新しい cwd 推測値を作ること。
- サーバー側で cwd ごとの件数や grouped response を返すこと。
- セッション一覧の pagination 導入や large dataset 対応の最適化。

## Upstream / Downstream
- **Upstream**: `session-api-db-query` による保存済み read model 参照の一覧 API、`session-date-filtering` による日付条件管理、`session-full-text-search` による検索条件管理、`session-execution-directory-search` による cwd メタデータの一覧 response 利用可能性。
- **Downstream**: 将来の `GET /api/sessions/directories` のような directory summary endpoint、pagination 導入時の server-side aggregation、repository / branch / model 専用フィルタ。

## Existing Spec Touchpoints
- **Extends**: なし。既存 Spec は履歴として残し、今回の責務は新規 Spec として扱う。
- **Adjacent**: `frontend-session-ui` は一覧・詳細の基本閲覧体験、`session-date-filtering` は日付範囲、`session-full-text-search` は検索語、`session-execution-directory-search` は cwd 表示と検索の既存 contract を扱う。

## Constraints
backend endpoint と DB schema は初回実装では変更しない。

タブ切り替えは追加 API request を発生させず、取得済み一覧に対するローカル UI state として扱う。

日付範囲、検索語、同期後 refresh、loading / empty / error の既存 contract を維持する。

`cwd` が `null` または空白のセッションは落とさず、`ディレクトリ未設定` にまとめる。

テストを追加・更新するときは、各 `it` / test case の直前に `概要・目的`、`テストケース`、`期待値` のコメントを残す。

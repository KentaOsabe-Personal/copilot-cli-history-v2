# 調査・設計判断ログ

## Summary
- **Feature**: `session-full-text-search`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 既存の `copilot_sessions` は `summary_payload` / `detail_payload` と scalar metadata を保持しており、本文検索用テキストは raw files ではなく read model 再生成時に作れる。
  - `GET /api/sessions` は `SessionListParams` と `SessionIndexQuery` で日付範囲を扱い、frontend は `useSessionIndex` と `SessionDateFilterForm` で applied range を維持しているため、検索条件も同じ一覧条件として統合できる。
  - 初期実装では外部検索サービスや MySQL FULLTEXT を採用せず、正規化済み `search_text` と literal substring match を使うことで、ランキング・parser・CJK tokenization の責務をこの spec に持ち込まない。

## Research Log

### 既存 read model と同期境界
- **Context**: 要件1は、明示同期で保存または更新されたセッションを検索可能にすることを求める。
- **Sources Consulted**:
  - `.kiro/steering/product.md`
  - `.kiro/steering/tech.md`
  - `.kiro/specs/history-db-read-model/design.md`
  - `.kiro/specs/history-sync-api/design.md`
  - `backend/lib/copilot_history/persistence/session_record_builder.rb`
  - `backend/app/models/copilot_session.rb`
  - `backend/db/schema.rb`
- **Findings**:
  - raw files は一次ソース、DB read model は再生成可能な補助層として扱う方針が steering と既存 design に明記されている。
  - `SessionRecordBuilder` は同期時に `summary_payload` と `detail_payload` を作り、`CopilotSession` attributes として返している。
  - `CopilotSession` は scalar metadata、payload JSON、degraded / issue count をすでに持つが、検索専用テキスト列はない。
  - `HistorySyncService` は fingerprint 不変の session を skip するため、検索 projection の生成規則を変更しても通常の手動同期だけでは既存 row が再生成されない可能性がある。
- **Implications**:
  - 検索対象構築は `SessionRecordBuilder` から呼ばれる persistence 境界に置き、API request 時に raw files や presenter を再実行しない。
  - `search_text` は DB read model の再生成可能な補助情報として追加し、payload と同じ同期 lifecycle で更新する。
  - sync service は fingerprint が同じでも検索 projection version が古い row を update 対象にする。

### session list API 統合点
- **Context**: 要件2は、検索語と日付範囲を併用した一覧取得と既存 response shape の維持を求める。
- **Sources Consulted**:
  - `.kiro/specs/session-api-db-query/design.md`
  - `backend/app/controllers/api/sessions_controller.rb`
  - `backend/lib/copilot_history/api/session_list_params.rb`
  - `backend/lib/copilot_history/api/session_index_query.rb`
  - `backend/spec/requests/api/sessions_spec.rb`
- **Findings**:
  - `SessionListParams` は `from` / `to` / `limit` を正規化し、invalid query を `invalid_session_list_query` として返す。
  - `SessionIndexQuery` は `updated_at_source` 優先、欠落時 `created_at_source` fallback の候補を作り、安定 sort 後に `summary_payload` を返す。
  - request spec は DB read model passthrough と 200 empty response、400 invalid params を固定している。
- **Implications**:
  - `search` param は `SessionListParams` の正規化結果に追加し、既存 invalid list query envelope を拡張する。
  - `SessionIndexQuery` は date candidate scope に search scope を合成し、response envelope、meta、degraded / issue payload は変更しない。

### frontend 一覧条件と状態表示
- **Context**: 要件3・4は、一覧画面で検索語を適用・解除し、検索中・検索空・検索条件エラーを区別することを求める。
- **Sources Consulted**:
  - `.kiro/specs/session-date-filtering/design.md`
  - `frontend/src/features/sessions/hooks/useSessionIndex.ts`
  - `frontend/src/features/sessions/pages/SessionIndexPage.tsx`
  - `frontend/src/features/sessions/components/SessionDateFilterForm.tsx`
  - `frontend/src/features/sessions/components/SessionEmptyState.tsx`
  - `frontend/src/features/sessions/api/sessionApi.ts`
- **Findings**:
  - `useSessionIndex` は applied date range、query-keyed reusable snapshot、same-range reload を持つ。
  - `SessionIndexPage` は date filter form、sync control、loading / empty / error / success 表示を統合している。
  - `sessionApi` は `from` / `to` query serialization を担当し、`SessionIndexQuery` 型は date range だけを持つ。
- **Implications**:
  - date range と検索語をまとめた `SessionIndexCriteria` を hook の基準にし、query key は range と normalized search term の両方から作る。
  - 検索語を変える `applySearch` は current date range を維持し、別検索語の成功 snapshot を新条件の確定結果として表示しない。
  - empty state は「検索語ありの空」と「日付条件だけの空」を分け、search condition error は generic fetch failure と別の copy / action で示す。

### 検索方式の選択
- **Context**: 要件5は、初期検索を read-only 一覧絞り込みに閉じ、ランキング・ハイライト・semantic search・外部サービスを必須にしないことを求める。
- **Sources Consulted**:
  - `.kiro/steering/product.md`
  - `.kiro/steering/tech.md`
  - `.kiro/specs/session-full-text-search/brief.md`
  - `docker-compose.yml`
- **Findings**:
  - 技術スタックは Rails API / MySQL / React で、新規検索サービスは steering に含まれていない。
  - MySQL FULLTEXT は将来の選択肢になり得るが、初期要件はランキングや parser tuning を要求しない。
  - 利用対象はローカル履歴であり、初期実装では検索性能より既存境界と検索対象の明確さが重要である。
- **Implications**:
  - 初期実装は `search_text` に対する escaped `LIKE` literal substring match とする。
  - 検索語と保存テキストは前後空白の trim と空白 collapse を行い、`%` / `_` は wildcard ではなく文字として扱う。
  - 大量履歴で性能問題が確認された場合は、`search_text` contract を維持したまま MySQL FULLTEXT や別 index へ移行できる。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 正規化 `search_text` + literal substring match | 同期時に検索対象を 1 列へ集約し、一覧 query で `LIKE` 条件を追加する | raw files を読まない、外部依存なし、検索対象が明示的、CJK でも token parser に依存しない | `%term%` は index を効かせにくい、大量データでは性能検証が必要 | 初期採用 |
| MySQL FULLTEXT index | `search_text` に FULLTEXT index を追加し、`MATCH AGAINST` で検索する | 大量テキストで性能を出しやすい、後続 ranking に接続しやすい | parser・stopword・CJK tokenization・score semantics が設計責務になる | 後続最適化候補 |
| summary/detail JSON 直接検索 | 保存済み payload JSON を query 時に文字列化または JSON path で検索する | schema 追加を抑えられる | query が重い、検索対象境界が曖昧、payload shape drift の影響が大きい | 不採用 |
| 外部検索サービス | SQLite FTS / OpenSearch など別 index を持つ | 高度な検索・ランキングに拡張しやすい | ローカル開発・同期・運用境界が大きく増える | 要件5により不採用 |

## Design Decisions

### Decision: 検索対象を `copilot_sessions.search_text` に保存する
- **Context**: 一覧検索は保存済み read model を参照し、raw files を直接検索しない必要がある。
- **Alternatives Considered**:
  1. `detail_payload` JSON を query 時に検索する。
  2. 同期時に本文検索用の検索対象テキストを構築して列に保存する。
- **Selected Approach**: `CopilotHistory::Persistence::SessionSearchTextBuilder` が summary/detail payload の会話本文・会話 preview・issue code / message から検索対象を集約し、`CopilotSession.search_text` に保存する。
- **Rationale**: 検索対象の所有者が明確になり、query path は DB read model 参照だけで完結する。
- **Trade-offs**: payload contract が変わると builder の whitelist 更新が必要になる。代わりに、検索対象外の raw JSON や UI 表示都合が検索へ漏れにくい。
- **Follow-up**: builder spec で会話本文、会話 preview、issue code / message の対象 field と、tool call、activity、work context、selected model、raw payload の非対象 field を固定する。

### Decision: 検索 projection version が古い row は同期 skip しない
- **Context**: 既存 read model rows は migration 直後または生成規則変更後に古い `search_text` を持ち、source fingerprint は raw files と一致している場合がある。
- **Alternatives Considered**:
  1. migration 時に JSON payload から全 row を backfill する。
  2. `search_text_version` を追加し、次回明示同期時にも version 不一致なら fingerprint 不変でも update する。
- **Selected Approach**: migration で既存 rows を本文検索用に backfill し、`HistorySyncService` の skip 判定へ「既存 row の検索 projection version が古ければ update」を追加する。
- **Rationale**: app code を使う複雑な data migration を避けつつ、利用者が既存の手動同期導線で検索可能状態へ移行できる。
- **Trade-offs**: 初回の同期後に saved_count / updated_count が増える。これは read model projection の再生成であり、raw files 正本方針とは矛盾しない。
- **Follow-up**: 将来 `search_text` 生成規則に破壊的変更がある場合は、`search_text_version` を進める migration か明示 reindex spec を検討する。

### Decision: 初期検索は literal substring match とする
- **Context**: 検索結果スコアリング、semantic search、外部検索サービスは対象外である。
- **Alternatives Considered**:
  1. MySQL FULLTEXT を初期から使う。
  2. 正規化 text に対する escaped `LIKE` を使う。
- **Selected Approach**: normalized search term を wildcard escape し、`search_text LIKE "%term%"` 相当の literal substring 条件として扱う。
- **Rationale**: ローカル履歴の初期探索に必要な「覚えている断片で絞る」体験を、追加サービスや parser tuning なしで満たす。
- **Trade-offs**: 大量データでは query performance の再検証が必要になる。
- **Follow-up**: 検索性能が問題化した場合は `search_text` contract を維持しつつ FULLTEXT index へ移行する別 spec を切る。

### Decision: date range と search term を 1 つの一覧 criteria として扱う
- **Context**: 検索は日付範囲と併用でき、同期後再取得でも条件を維持する必要がある。
- **Alternatives Considered**:
  1. 検索専用 hook を別に作り、date filter と page で合成する。
  2. `useSessionIndex` の applied criteria を date range + search term に拡張する。
- **Selected Approach**: `useSessionIndex` が `SessionIndexCriteria` を所有し、`applyRange`、`applySearch`、`clearSearch`、`reloadSessions` は同じ criteria ref / query key を使う。
- **Rationale**: 既存の race cancellation、snapshot reuse、same-range reload の考え方を維持し、別検索語の結果を current result として残さない条件を hook 境界で保証できる。
- **Trade-offs**: date filter helper は criteria helper へ広がるが、API / page / component にばらけるより保守しやすい。
- **Follow-up**: URL persistence や pagination を追加する場合は criteria contract の再検証が必要である。

## Synthesis Outcomes

### Generalization
- 日付範囲と検索語は別々の UI 部品だが、API request と reusable snapshot の観点では同じ「一覧 criteria」である。設計では `SessionIndexCriteria` と query key を導入し、current requirements では date + search だけを扱う。
- 検索対象構築は、会話本文・会話 preview・issue code / message に限定した本文検索 projection とする。tool call、activity、work context、model はノイズを増やすため既定検索対象に含めず、任意 JSON 全体検索にも広げない。

### Build vs Adopt
- 検索 UI / state は既存 React hook と component を拡張して構築する。新しい state management library は採用しない。
- backend 検索は既存 ActiveRecord / MySQL を使って構築する。外部検索エンジン、semantic search library、MySQL FULLTEXT は初期採用しない。

### Simplification
- 検索結果 score、match count、highlight fragment、専用 sort は設計から除外する。
- 検索条件は frontend の local state に閉じ、URL / localStorage / backend 永続化を追加しない。
- `SearchTextBuilder` は 1 つの保存列を作る責務だけを持ち、query execution や UI 表示文言を持たない。

## Risks & Mitigations
- `%term%` search が大量履歴で遅くなる — 初期は local read model の範囲に限定し、performance issue が確認されたら `search_text` contract を維持して MySQL FULLTEXT 等を別 spec で検討する。
- 検索対象 whitelist が payload 変更に追随しない — builder spec で対象 field を固定し、payload contract 変更を revalidation trigger にする。
- 既存 rows の `search_text` が古い生成規則のまま残る — migration が本文検索用に backfill し、sync service が `search_text_version` の不一致を update 対象として扱う。
- 検索語変更中に古い検索結果が表示される — hook が request id / AbortController / criteria key を使い、別 criteria の結果を current state に採用しない。
- 検索条件エラーと通常取得失敗が混同される — backend details `field: "search"` と frontend state classification で search condition error を分ける。

## References
- `.kiro/steering/product.md` — raw files 正本、DB read model 補助層、read-only 閲覧原則。
- `.kiro/steering/tech.md` — Rails API / MySQL / React / Docker Compose とテスト標準。
- `.kiro/steering/structure.md` — backend `lib/copilot_history` と frontend feature slice の配置方針。
- `.kiro/specs/history-db-read-model/design.md` — `CopilotSession` と `SessionRecordBuilder` の保存境界。
- `.kiro/specs/history-sync-api/design.md` — 明示同期 lifecycle と read model 更新境界。
- `.kiro/specs/session-api-db-query/design.md` — `GET /api/sessions` の DB query / date range / response envelope。
- `.kiro/specs/session-date-filtering/design.md` — frontend applied range、query-keyed snapshot、sync 後 reload の既存拡張。

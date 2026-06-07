# 調査と設計判断

## 概要
- **Feature**: `api-contract-fixtures`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 現行 API contract は Rails request specs、backend presenter specs、frontend `sessionApi.types.ts` / API client tests に分散しており、後続 Django / BigQuery 移行が参照できる単一の fixture 正本がない。
  - frontend 型と現行 presenter contract は `work_context`、`selected_model`、`conversation`、`activity`、`timeline`、`raw_included` を正本にしている。一方で一部 DB passthrough request spec には古い `workspace` / `model` 例が残るため、fixture では採用根拠と差分を contract note に明記する必要がある。
  - Error envelope は `{ error: { code, message, details } }` で統一されるが、history sync の root failure / persistence failure は top-level `meta.sync_run` と `meta.counts` を追加で持つ。

## 調査ログ

### 現行 API / frontend 型の契約源
- **Context**: fixture の正本を決めるため、API response shape がどこで固定されているか確認した。
- **Sources Consulted**:
  - `frontend/src/features/sessions/api/sessionApi.types.ts`
  - `frontend/src/features/sessions/api/sessionApi.ts`
  - `frontend/tests/features/sessions/api/sessionApi.test.ts`
  - `backend/lib/copilot_history/api/presenters/session_index_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/session_detail_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/history_sync_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/error_presenter.rb`
- **Findings**:
  - `SessionIndexResponse` は top-level `data` 配列と `meta` object を持ち、summary item は `work_context`、`selected_model`、`conversation_summary`、`degraded`、`issues` を含む。
  - `SessionDetailResponse` は top-level `data` object を持ち、`conversation.entries`、`activity.entries`、`timeline`、`raw_included`、`raw_payload` の raw opt-in contract を含む。
  - `HistorySyncResponse` は `data.sync_run` と `data.counts` を持ち、sync failure の一部は error envelope と `meta` を併用する。
  - frontend API client は 404 `session_not_found` だけを `kind: "not_found"` として正規化し、それ以外の HTTP error は backend error として扱う。
- **Implications**:
  - fixture の期待値は frontend 型と現行 presenter contract を基準にする。
  - request spec に残る旧 payload 例は契約正本ではなく、contract note の差分記録対象にする。

### 対象 endpoint と scenario の抽出
- **Context**: 要件 1〜5 は list/detail/raw/sync/error の代表 fixture を求めている。
- **Sources Consulted**:
  - `backend/spec/requests/api/sessions_spec.rb`
  - `backend/spec/requests/api/history_syncs_spec.rb`
  - `backend/spec/lib/copilot_history/api/session_list_params_spec.rb`
  - `backend/spec/lib/copilot_history/api/presenters/session_index_presenter_spec.rb`
  - `backend/spec/lib/copilot_history/api/presenters/session_detail_presenter_spec.rb`
  - `backend/spec/lib/copilot_history/api/presenters/history_sync_presenter_spec.rb`
- **Findings**:
  - `GET /api/sessions` は成功、空結果、degraded session、date range、search、検索該当なし、invalid query を fixture 化する必要がある。
  - `GET /api/sessions/:id` は通常 detail、missing 404、raw omitted を固定し、`include_raw=true` は同じ DTO shape で raw payload が実値になることを示す必要がある。
  - `POST /api/history/sync` は success、completed_with_issues、running conflict、root failure、persistence failure を固定する必要がある。
  - invalid list query の `details` は `field`、`reason`、必要に応じて `value` を持つ。
- **Implications**:
  - fixture は endpoint 別だけでなく scenario 別に分け、request、response、HTTP status、型対応を追いやすくする。
  - status code / error code 対応表は contract note にまとめ、frontend error normalization の根拠にする。

### 既存 spec と migration roadmap
- **Context**: 後続 Django / BigQuery spec がこの fixture をどのように参照するか確認した。
- **Sources Consulted**:
  - `.kiro/steering/roadmap.md`
  - `.kiro/specs/api-contract-fixtures/brief.md`
  - `.kiro/specs/django-presenters-contract/brief.md`
  - `.kiro/specs/django-history-api/brief.md`
  - `.kiro/specs/session-api-db-query/design.md`
  - `.kiro/specs/history-sync-api/design.md`
- **Findings**:
  - roadmap は `api-contract-fixtures` を Django presenter / API / parity validation の前提 spec として置いている。
  - 現行 Rails / MySQL は残したまま、Django 側が同じ fixture を期待値として使えることが目的である。
  - BigQuery schema や Django repository の設計は後続 spec の責務であり、この spec に datastore 前提を埋め込むと境界が広がる。
- **Implications**:
  - fixture は実装言語や datastore から独立した JSON 契約資料として `.kiro/specs/api-contract-fixtures/` に保存する。
  - 後続 spec は fixture を read-only expectation として参照し、fixture の変更は仕様変更候補として扱う。

### Steering とテスト規約
- **Context**: 追加する artifact と検証手順が project memory に合うか確認した。
- **Sources Consulted**:
  - `.kiro/steering/product.md`
  - `.kiro/steering/tech.md`
  - `.kiro/steering/structure.md`
  - `AGENTS.md`
- **Findings**:
  - raw files は一次ソース、DB / BigQuery は再生成可能 read model として扱う。
  - frontend は `features/sessions` の API 型に依存し、API base URL と JSON shape を明示 contract として扱う。
  - テストを追加・更新する場合は各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントが必要である。
- **Implications**:
  - contract fixture は現行 API shape を保存するが、API shape 変更や datastore 移行そのものは扱わない。
  - fixture 構文検証や型対応検証を追加する場合も、プロジェクトのテストコメント規約を設計に含める。

## アーキテクチャパターン評価

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Request spec 参照のみ | 後続実装が Rails request specs を読む | 追加 artifact が少ない | frontend 型との対応や代表 scenario が分散したまま残る | 不採用 |
| OpenAPI schema 化 | endpoint schema を OpenAPI として定義する | ツール連携しやすい | 現行目的は代表 fixture と差分判定であり、OpenAPI 導入コストが大きい | 不採用 |
| JSON fixture + contract note | scenario 別 JSON と日本語 note で契約を固定する | 後続 Django / parity validation が期待値として使いやすい | schema validation は別途軽量チェックが必要 | 採用 |
| Rails から自動再生成 | request specs から fixture を生成する | drift を減らせる | 初期実装が重く、現行 spec はまず契約資料保存を求めている | 更新手順として記録し、初期は手動更新を許容 |

## 設計判断

### 判断: fixture は `.kiro/specs/api-contract-fixtures/fixtures/` に保存する
- **Context**: 後続 Django presenter / API / parity validation が Rails 実装から独立して期待値を参照する必要がある。
- **Alternatives Considered**:
  1. `backend/spec/fixtures` に置く — Rails 側には自然だが Django 側からは Rails 実装配下に見える。
  2. `frontend/tests` に置く — frontend 型との近さはあるが sync / backend error 契約が読みにくい。
  3. spec 配下に置く — Kiro spec の契約 artifact として境界が明確になる。
- **Selected Approach**: `.kiro/specs/api-contract-fixtures/fixtures/` に endpoint / scenario 別 JSON を置き、`.kiro/specs/api-contract-fixtures/contract.md` で対応表と更新手順を持つ。
- **Rationale**: 仕様資料と期待値を同じ spec 境界に閉じ、後続 spec が read-only 参照しやすい。
- **Trade-offs**: 実装テスト fixture とは別管理になるため、軽量な JSON 構文・必須 field 検証を追加して drift を抑える。
- **Follow-up**: task 生成時に fixture index と validation spec を同じ task 境界に含める。

### 判断: 期待値は frontend 型と presenter contract を正本にする
- **Context**: 一部 request spec には `workspace` / `model` の passthrough 例が残るが、frontend 型は `work_context` / `selected_model` を使っている。
- **Alternatives Considered**:
  1. request spec の全 payload 例をそのまま fixture 化する
  2. frontend 型だけを fixture 化する
  3. frontend 型と presenter contract を正本にし、差分を note に記録する
- **Selected Approach**: `sessionApi.types.ts` と presenter specs に一致する shape を代表 fixture とし、旧 naming / passthrough 例は contract note の差分として扱う。
- **Rationale**: 利用者から見える frontend 依存 contract を維持する目的に合い、後続 Django 実装の期待値が明確になる。
- **Trade-offs**: Rails request spec の一部例とは一致しない箇所が残る。実装時に現行 API 出力を確認し、差分が本物なら contract note に根拠を追記する。
- **Follow-up**: fixture 更新時は影響する frontend 型と status / error code の変更有無を必ず記録する。

### 判断: raw opt-in は同一 detail DTO の差分 fixture として固定する
- **Context**: 通常 detail と raw opt-in は endpoint が同じで query parameter だけが異なる。
- **Alternatives Considered**:
  1. raw を別 endpoint として記録する
  2. raw field を通常 detail から省略する
  3. 通常 detail は `raw_payload: null`、raw opt-in は `raw_payload` 実値として同じ DTO shape を記録する
- **Selected Approach**: `GET /api/sessions/:id` と `GET /api/sessions/:id?include_raw=true` の response fixture を並べ、`raw_included` と raw payload field の違いだけを明示する。
- **Rationale**: frontend 型と現行 presenter の contract に一致し、通常表示が raw payload を要求しない境界も表現できる。
- **Trade-offs**: fixture が大きくなりやすいため、代表 raw payload は最小限に留める。
- **Follow-up**: 後続 parity validation は raw omitted / raw included の両方を比較対象にする。

### 判断: fixture validation は JSON 構文と契約必須 field の軽量検証に限定する
- **Context**: この spec は API 実装変更ではなく契約資料保存が目的である。
- **Alternatives Considered**:
  1. 完全 JSON Schema を導入する
  2. 検証を一切追加しない
  3. 既存 test runner で fixture JSON と必須 field / status code を軽量検証する
- **Selected Approach**: backend RSpec に fixture contract spec を追加し、JSON parse、scenario index、必須 top-level field、status / error code 対応を検証する。
- **Rationale**: 新規依存なしで fixture の破損を検出でき、プロジェクトの既存 CI に乗る。
- **Trade-offs**: TypeScript 型との完全一致までは保証しない。型対応表と representative field validation で今回の範囲を満たす。
- **Follow-up**: OpenAPI / JSON Schema 化は後続で必要性が出た場合の revalidation trigger とする。

## リスクと緩和策
- request spec、presenter、frontend 型の間に既存 drift があるリスク — fixture の期待値根拠を contract note に明記し、差分は仕様変更ではなく観測差分として記録する。
- fixture が現行 API と再び drift するリスク — 更新手順、影響型、status / error code 変更有無、validation spec を導入する。
- fixture が後続 Django 実装の都合で拡張されるリスク — `.kiro/specs/api-contract-fixtures/` は read-only expectation とし、shape 変更は仕様変更候補として扱う。
- raw payload fixture が大きくなりすぎるリスク — raw opt-in の代表 payload は field presence と null/実値差分を示す最小例に限定する。

## 参考資料
- `.kiro/steering/product.md` — raw files 正本、read model、degraded data の扱い。
- `.kiro/steering/tech.md` — React / TypeScript / Rails / MySQL と API contract 方針。
- `.kiro/steering/structure.md` — frontend feature slice、backend API / presenter 境界、spec artifact の置き場所。
- `.kiro/steering/roadmap.md` — Django / BigQuery 移行における `api-contract-fixtures` の依存順。
- `frontend/src/features/sessions/api/sessionApi.types.ts` — frontend が依存する API DTO 型。
- `backend/lib/copilot_history/api/presenters/*` — 現行 Rails presenter contract。
- `backend/spec/requests/api/*` — HTTP status、error code、代表 request の既存検証。

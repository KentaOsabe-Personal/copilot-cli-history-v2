# 要件ドキュメント

## 導入

Rails / MySQL から Django / BigQuery へ移行する開発者と frontend 保守者は、現行 frontend が依存する API request / response shape と HTTP status code を移行後も維持する必要がある。現在の API contract は Rails request specs、presenter、frontend の `sessionApi.types.ts`、hooks / pages に分散しており、契約 fixture がないまま移植を始めると、Django 側の差分が仕様変更なのか移植バグなのか判定しにくい。

この spec は、現行 API と frontend 型を正本として、`POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id`、`GET /api/sessions/:id?include_raw=true` の代表 request / response fixture と contract note を保存する。fixture は後続の Django presenter / API / parity validation が同じ期待値を参照できる契約資料として扱い、API shape の変更や移行先実装そのものは扱わない。

## 境界コンテキスト

- **In scope**: 現行 API endpoint の contract inventory、代表 request / response fixture、HTTP status code と error code の一覧、frontend 型との対応表、fixture 更新手順。
- **Out of scope**: API shape の変更、新規 UI 機能、Django backend 実装、BigQuery schema、Python reader 移植、Rails / MySQL 削除。
- **Adjacent expectations**: 後続の Django presenter / API / parity validation は、この spec が保存する fixture を期待値として参照できること。現行 Rails API と frontend 型に矛盾が見つかった場合、この spec は差分を contract note に記録し、どちらかへ仕様変更する判断は後続 spec または人間レビューに委ねること。

## 要件

### Requirement 1: API 契約インベントリ

**Objective:** As a 移行開発者, I want 現行 API endpoint ごとの契約範囲を一覧できる, so that 後続実装が fixture の対象と非対象を誤読しない

#### Acceptance Criteria

1. The API contract fixture set shall `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id`、`GET /api/sessions/:id?include_raw=true` を対象 endpoint として明示する。
2. The API contract fixture set shall 各対象 endpoint について、代表 request、期待 HTTP status code、成功 payload または error envelope のいずれを検証する fixture かを明示する。
3. The API contract fixture set shall API shape 変更、新規 UI 機能、移行先 backend 実装、分析用 schema、reader 移植、既存 stack 削除を対象外として明示する。
4. If 現行 API と frontend 型の間に命名、nullable、または field presence の差分が見つかった場合, then the API contract fixture set shall その差分を contract note に記録し、fixture の期待値がどちらに基づくかを明示する。

### Requirement 2: セッション一覧契約 fixture

**Objective:** As a frontend 保守者, I want session list の成功・空結果・劣化結果・検索条件の契約 fixture を確認できる, so that 一覧 UI が依存する response shape を移行後も維持できる

#### Acceptance Criteria

1. When `GET /api/sessions` の list success fixture を確認する, the API contract fixture set shall top-level `data` 配列と `meta` object を含む期待 response を示す。
2. When list success fixture includes session summaries, the API contract fixture set shall `id`、`source_format`、`created_at`、`updated_at`、`work_context`、`selected_model`、`source_state`、`event_count`、`message_snapshot_count`、`conversation_summary`、`degraded`、`issues` を frontend が参照できる形で示す。
3. When list fixture represents no matching sessions, the API contract fixture set shall HTTP 200 と `data: []`、`meta.count: 0`、`meta.partial_results: false` の期待 response を示す。
4. When list fixture represents degraded sessions, the API contract fixture set shall `degraded: true`、session-level `issues`、および `meta.partial_results: true` の期待 response を示す。
5. When list fixture includes date range or search query requests, the API contract fixture set shall request query と期待 response の対応を示し、該当なしは error ではなく空の成功 response になることを示す。

### Requirement 3: セッション詳細と raw opt-in fixture

**Objective:** As a frontend 保守者, I want detail と raw opt-in の response 契約を同じ fixture 群で確認できる, so that 通常詳細表示と raw payload 表示の境界を維持できる

#### Acceptance Criteria

1. When `GET /api/sessions/:id` の detail success fixture を確認する, the API contract fixture set shall top-level `data` object と session detail fields の期待 response を示す。
2. When detail success fixture includes conversation data, the API contract fixture set shall `conversation.entries`、`conversation.message_count`、`conversation.empty_reason`、`conversation.summary` の期待 shape を示す。
3. When detail success fixture includes activity and timeline data, the API contract fixture set shall `activity.entries` と `timeline` の sequence、kind/category、mapping status、occurred_at、tool calls、degraded、issues の期待 shape を示す。
4. When `GET /api/sessions/:id?include_raw=true` の fixture を確認する, the API contract fixture set shall `raw_included: true` と raw payload fields が返る箇所を示す。
5. When raw opt-in is not requested, the API contract fixture set shall raw payload fields が `null` または非表示相当として扱われる期待 response を示し、通常詳細表示が raw payload を要求しないことを明示する。

### Requirement 4: 履歴同期契約 fixture

**Objective:** As a 移行開発者, I want history sync の成功・競合・失敗契約を fixture で確認できる, so that 移行後の同期 API が frontend と運用者の期待を壊さない

#### Acceptance Criteria

1. When `POST /api/history/sync` succeeds, the API contract fixture set shall HTTP 200 と `data.sync_run`、`data.counts` を含む期待 response を示す。
2. When sync succeeds with degraded sessions, the API contract fixture set shall HTTP 200、terminal status `completed_with_issues`、`degraded_count`、保存された issue 情報を含む期待 response を示す。
3. If another sync is already running, then the API contract fixture set shall HTTP 409 と `history_sync_running` error envelope を示し、既存 run の `sync_run_id` と `started_at` が details に含まれることを示す。
4. If history root cannot be read, then the API contract fixture set shall HTTP 503 と root failure code、message、path details、および sync run meta を含む期待 response を示す。
5. If sync persistence fails after a run is created, then the API contract fixture set shall HTTP 500 と `history_sync_failed` error envelope、および sync run meta を含む期待 response を示す。

### Requirement 5: Error envelope と validation 契約

**Objective:** As a frontend 保守者, I want error response の共通 envelope と validation error を確認できる, so that frontend の error normalization を移行後も変更せずに保てる

#### Acceptance Criteria

1. The API contract fixture set shall error response の top-level shape を `error.code`、`error.message`、`error.details` として示す。
2. If `GET /api/sessions/:id` targets a missing session, then the API contract fixture set shall HTTP 404 と `session_not_found` error envelope を示し、要求された session id が details に含まれることを示す。
3. If list request contains invalid date range, invalid datetime, invalid limit, overlong search, or display-hostile control characters, then the API contract fixture set shall HTTP 400 と `invalid_session_list_query` error envelope を示す。
4. When validation error fixture を確認する, the API contract fixture set shall `details.field`、`details.reason`、および該当する場合の `details.value` を示す。
5. The API contract fixture set shall frontend が 404 `session_not_found` を dedicated not-found state として扱い、それ以外の backend error を backend error として扱えるだけの code と status の対応を示す。

### Requirement 6: Frontend 型対応契約

**Objective:** As a frontend 保守者, I want fixture fields と frontend 型の対応を確認できる, so that fixture 更新時に UI 依存 field の欠落を検出できる

#### Acceptance Criteria

1. The API contract fixture set shall list response fixture と `SessionIndexResponse`、`SessionSummary`、`SessionIssue`、`WorkContext`、`SessionConversationSummary` の対応を示す。
2. The API contract fixture set shall detail response fixture と `SessionDetailResponse`、`SessionDetail`、`SessionConversation`、`SessionActivity`、`SessionTimelineEvent`、tool call 関連型の対応を示す。
3. The API contract fixture set shall sync response fixture と `HistorySyncResponse`、`HistorySyncRun`、`HistorySyncCounts` の対応を示す。
4. The API contract fixture set shall error fixture と `ErrorEnvelope`、frontend error normalization が依存する status code と error code の対応を示す。
5. If frontend 型に存在する field が代表 fixture に含まれない場合, then the API contract fixture set shall その field が対象外なのか、別 fixture で検証されるのか、または契約欠落なのかを contract note で明示する。

### Requirement 7: Fixture 更新とレビュー手順

**Objective:** As a 移行開発者, I want fixture の更新条件と確認手順を理解できる, so that 契約変更と移植バグを分けて扱える

#### Acceptance Criteria

1. The API contract fixture set shall fixture の正本が現行 API と frontend 型であることを明示する。
2. When fixture is regenerated or manually updated, the API contract fixture set shall 更新理由、対象 endpoint、影響する frontend 型、期待 status code の変更有無を記録する手順を示す。
3. If fixture update changes request shape, response shape, status code, or error code, then the API contract fixture set shall その変更を仕様変更候補として明示し、後続実装の parity failure と区別できるようにする。
4. The API contract fixture set shall 後続 Django presenter / API / parity validation が同じ fixture を期待値として参照する前提を明示する。
5. Where tests are added or updated for this spec, the API contract fixture set shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す project rule を示す。

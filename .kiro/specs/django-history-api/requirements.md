# 要件ドキュメント

## 導入

この Spec は、Rails / MySQL から Django / BigQuery へ backend を切り替える過程で、現行 frontend が利用する履歴 API 契約を維持するための HTTP API 要件を定義する。対象は `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/:id`、`GET /api/sessions/:id?include_raw=true` である。

目的は、frontend の一覧・詳細・同期 UI を作り直さずに、保存済み read model と既存 presenter 契約を利用する API として同じ URL、HTTP status code、JSON shape、error envelope を返せる状態にすることである。実装方式の詳細は design に委ね、この文書では利用者、frontend、運用者、移行開発者から観測できる振る舞いを固定する。

## 境界コンテキスト

- **In scope**: 履歴同期 API、セッション一覧 API、セッション詳細 API、raw payload opt-in、request query validation、HTTP status と error envelope、frontend 開発 URL からの接続許可、fake repository を使う API テスト、既存 contract fixture との照合、BigQuery repository を使う opt-in integration の入口。
- **Out of scope**: raw reader の新規移植、presenter response shape の再定義、BigQuery schema 作成、repository の BigQuery 実装、Rails / Django 差分レポート、Rails / MySQL 削除、frontend UI の作り直し、認証・認可、background sync、Django admin / auth / session。
- **Adjacent expectations**: `django-presenters-contract` は成功・失敗レスポンス本文の shape を提供する。`bigquery-session-repository` は保存済み read model の一覧、詳細、同期保存、running sync lookup の契約を提供する。`api-contract-fixtures` は Rails 互換の期待値として参照される。frontend は既存 `sessionApi` 契約の URL、status、payload を利用する。

## 要件

### Requirement 1: Rails 互換 endpoint 契約

**Objective:** As a 移行開発者, I want Django History API が現行 Rails API と同じ endpoint 契約を提供する, so that frontend 変更を混ぜずに backend 移行を検証できる

#### Acceptance Criteria

1. When クライアントが `POST /api/history/sync` を要求する, the Django History API shall 現行同期 API と同じ URL で履歴同期要求を受け付ける。
2. When クライアントが `GET /api/sessions` を要求する, the Django History API shall 現行一覧 API と同じ URL でセッション一覧を返す。
3. When クライアントが `GET /api/sessions/:id` を要求する, the Django History API shall 現行詳細 API と同じ URL で対象セッション詳細を返す。
4. When クライアントが `GET /api/sessions/:id?include_raw=true` を要求する, the Django History API shall 現行 raw opt-in 詳細 API と同じ URL と query contract で対象セッション詳細を返す。
5. The Django History API shall 対象 endpoint の成功 response、error response、HTTP status code を既存 contract fixture と照合できる互換契約として維持する。

### Requirement 2: セッション一覧取得と query 条件

**Objective:** As a 履歴参照アプリ利用者, I want 保存済み read model から条件に合うセッション一覧を取得したい, so that backend 切替後も同じ一覧画面で履歴を探せる

#### Acceptance Criteria

1. When クライアントが有効な `from` と `to` を指定して一覧を要求する, the Django History API shall 指定期間に一致する保存済みセッションを既存一覧 response shape で返す。
2. When クライアントが有効な `search` を指定して一覧を要求する, the Django History API shall 検索語に一致する保存済みセッションだけを一覧 response に含める。
3. When 一覧条件に一致するセッションが存在しない, the Django History API shall HTTP 200 と `data: []`、`meta.count: 0`、`meta.partial_results: false` を返す。
4. When 一覧 response にセッション要約を含める, the Django History API shall `id`、`source_format`、`created_at`、`updated_at`、`work_context`、`selected_model`、`source_state`、`event_count`、`message_snapshot_count`、`conversation_summary`、`degraded`、`issues` を frontend が参照できる形で返す。
5. When 一覧 response に degraded session が含まれる, the Django History API shall 該当 session の `degraded` と `issues` を保持し、`meta.partial_results` を true にする。
6. The Django History API shall 一覧取得を read-only 操作として扱い、一覧要求だけで raw files または保存済み read model を変更しない。

### Requirement 3: セッション詳細取得と raw payload opt-in

**Objective:** As a 履歴参照アプリ利用者, I want セッション詳細と必要時の raw payload を同じ契約で取得したい, so that 会話、activity、timeline、raw 確認を backend 差分なく利用できる

#### Acceptance Criteria

1. When クライアントが存在する session ID の詳細を要求する, the Django History API shall 対象 session の header、message snapshots、conversation、activity、timeline、degraded 状態、issue 情報を既存詳細 response shape で返す。
2. When 詳細 response に conversation を含める, the Django History API shall `conversation.entries`、`conversation.message_count`、`conversation.empty_reason`、`conversation.summary` を frontend 型と互換の形で返す。
3. When 詳細 response に activity と timeline を含める, the Django History API shall sequence、kind または category、mapping status、occurred_at、tool calls、degraded、issues を既存詳細契約で返す。
4. When raw opt-in が指定されない, the Django History API shall `raw_included` を false にし、raw payload fields を通常詳細表示で利用されない値として返す。
5. When `include_raw=true` が指定される, the Django History API shall `raw_included` を true にし、保存済み raw payload が存在する箇所へ raw value を含める。
6. If 指定された session ID が保存済み read model に存在しない, then the Django History API shall HTTP 404 と `session_not_found` error envelope を返す。

### Requirement 4: 履歴同期 API

**Objective:** As a 利用者, I want 明示操作でローカル履歴を保存済み read model に同期したい, so that BigQuery 移行後も同期 UI が成功、部分劣化、競合、失敗を同じ契約で扱える

#### Acceptance Criteria

1. When クライアントが履歴同期を要求する, the Django History API shall 同期処理を request 内で完了させ、同期実行状態と件数を含む response を返す。
2. When 同期が成功する, the Django History API shall HTTP 200 と `data.sync_run`、`data.counts` を含む成功 response を返す。
3. When 同期が degraded session を含んで完了する, the Django History API shall error envelope ではなく HTTP 200 の成功 response を返し、`sync_run.status` と `counts.degraded_count` に部分劣化を反映する。
4. While 未完了の同期実行が存在する, the Django History API shall 新しい同期要求を HTTP 409 と `history_sync_running` error envelope で拒否する。
5. If 履歴ルートを解決または読取できない, then the Django History API shall 空の同期成功ではなく root failure を識別できる失敗 response を返す。
6. If 同期保存が完了できない, then the Django History API shall `history_sync_failed` error envelope と同期実行 meta を含む失敗 response を返す。
7. The Django History API shall background job、進捗 polling、自動 file watch をこの feature の契約として提供しない。

### Requirement 5: Validation と error envelope

**Objective:** As a frontend 保守者, I want validation error と backend error が既存 envelope で返ってほしい, so that frontend の error normalization を変更せずに移行できる

#### Acceptance Criteria

1. The Django History API shall error response の top-level shape を `error.code`、`error.message`、`error.details` に固定する。
2. If 一覧 request の `from` または `to` が日時として解釈できない, then the Django History API shall HTTP 400 と `invalid_session_list_query` error envelope を返す。
3. If 一覧 request の日付 range が無効である, then the Django History API shall HTTP 400 と `invalid_session_list_query` error envelope を返す。
4. If 一覧 request の `limit` が許可範囲外である, then the Django History API shall HTTP 400 と `invalid_session_list_query` error envelope を返す。
5. If 一覧 request の `search` が長すぎる、または表示に適さない制御文字を含む, then the Django History API shall HTTP 400 と `invalid_session_list_query` error envelope を返す。
6. When validation error response を返す, the Django History API shall `details.field`、`details.reason`、および該当する場合の `details.value` を含める。
7. If repository または履歴読取に由来する失敗が発生する, then the Django History API shall frontend が not found、validation、conflict、service failure を code と status で区別できる error envelope を返す。

### Requirement 6: Frontend 接続と CORS

**Objective:** As a frontend 開発者, I want 既存 development URL から Django History API に接続したい, so that frontend の API base URL 設定を保ったまま移行確認できる

#### Acceptance Criteria

1. When frontend が設定済み API base URL から対象 endpoint を要求する, the Django History API shall browser から到達可能な HTTP response を返す。
2. When frontend の development origin から対象 endpoint が要求される, the Django History API shall local development で必要な cross-origin request を許可する。
3. When preflight request が必要な browser request が送信される, the Django History API shall frontend が対象 endpoint を呼び出せる CORS response を返す。
4. The Django History API shall この feature の契約として認証、認可、Django admin、server-side browser session を要求しない。
5. The Django History API shall frontend UI の画面構成、表示文言、状態管理の変更をこの feature の完了条件に含めない。

### Requirement 7: 契約検証と integration 入口

**Objective:** As a レビュー担当者, I want fake repository と contract fixture で Django History API の互換性を検証したい, so that BigQuery 実接続や frontend 改修に依存せず API 移行の妥当性を確認できる

#### Acceptance Criteria

1. When API tests が実行される, the Django History API shall fake repository を使って同期、一覧、詳細、raw opt-in、not found、validation、repository failure の代表挙動を検証できる。
2. When contract fixture tests が実行される, the Django History API shall `api-contract-fixtures` の対象 request / response と API response を比較できる。
3. When fixture と API response に差分がある, the Django History API shall 差分のある scenario、HTTP status、または field path をレビュー担当者が識別できる検証結果を返す。
4. Where 実 BigQuery repository を使う integration 検証が含まれる, the Django History API shall 明示 opt-in 条件が満たされた場合だけ実接続検証を行う。
5. If BigQuery credentials または dataset が開発者環境に存在しない, then the Django History API shall fake repository と contract fixture による主要 API 検証を継続できる。
6. When backend test case が追加または更新される, the Django History API shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを持つ。
7. The Django History API shall Rails / Django 差分レポート作成と Rails / MySQL stack 削除をこの feature の完了条件に含めない。

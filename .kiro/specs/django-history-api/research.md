# Research & Design Decisions

## Summary
- **Feature**: `django-history-api`
- **Discovery Scope**: Extension
- **Key Findings**:
  - Django foundation は `backend_config.urls`、`backend_config.settings`、pytest / ruff / mypy の入口を既に持ち、履歴 API route は未登録である。
  - `django-presenters-contract` と `bigquery-session-repository` は response body と repository port を分離済みであり、この feature は HTTP orchestration、validation、CORS、sync coordination に責務を限定できる。
  - `api-contract-fixtures` は Rails 互換の endpoint、status、body、error envelope を代表 fixture として保持しているため、API tests は fake repository と fixture loader を組み合わせる設計にする。

## Research Log

### 既存 Django runtime と route 境界
- **Context**: `POST /api/history/sync`、`GET /api/sessions`、`GET /api/sessions/<session_id>` を Django に追加する前提を確認した。
- **Sources Consulted**: `backend/backend_config/urls.py`、`backend/backend_config/settings.py`、`backend/tests/test_django_project_foundation.py`、`.kiro/specs/django-backend-foundation/design.md`
- **Findings**:
  - root URLconf は現時点で `/up` のみを公開し、履歴 API route は foundation spec の対象外としてテストされている。
  - settings は `MIDDLEWARE = []` で、admin / auth / session を前提にしていない。
  - `history_read_model` app は登録済みだが、履歴 API app はまだ存在しない。
- **Implications**:
  - 履歴 API は新規 Django app `history_api` として追加し、foundation の `/up` と分離する。
  - 認証、Django session、CSRF middleware へ依存せず、JSON API と CORS preflight を view / middleware 相当の薄い境界で扱う。

### Presenter と repository の統合点
- **Context**: Django API が response body を再実装せず Rails 互換 shape を返せるか確認した。
- **Sources Consulted**: `backend/copilot_history/api/response_projection.py`、`backend/copilot_history/api/presenters/*.py`、`backend/history_read_model/repository.py`、`backend/history_read_model/fake_repository.py`、`backend/history_read_model/bigquery_repository.py`
- **Findings**:
  - Presenter は `NormalizedSession` から body を生成するが、BigQuery repository の list/detail は保存済み `summary_payload` / `detail_payload` を `Mapping[str, object]` として返す。
  - repository は `SessionListCriteria`、`SessionDetailResult`、`SyncWriteResult`、`SyncRunLookupResult` などの typed result を持つ。
  - repository validation は BigQuery 実行前の欠落・不正条件を識別できるが、frontend 契約に合わせた `details.field` / `details.reason` は HTTP API 境界で整形する必要がある。
- **Implications**:
  - list/detail view は保存済み payload を envelope に包むだけにし、Presenter body shape の再投影を避ける。
  - sync view は Python reader、row builder、repository、HistorySyncPresenter を束ねる API service を置く。
  - repository error kind から HTTP status と error code への mapping を API 層の明示契約にする。

### Contract fixture と検証入口
- **Context**: Rails 互換性を実装前に検証可能にするため、fixture 利用方法を確認した。
- **Sources Consulted**: `.kiro/specs/api-contract-fixtures/fixtures/**`、`backend/tests/copilot_history/api_contract_fixtures.py`、`.kiro/specs/api-contract-fixtures/design.md`
- **Findings**:
  - fixture repository は scenario ID、method、endpoint、status、body を読み、差分 path を含む assertion helper を提供している。
  - frontend は `VITE_API_BASE_URL` から `/api/sessions`、`/api/sessions/<id>?include_raw=true`、`/api/history/sync` を呼び、error envelope を code/status で正規化する。
  - 主要 API 検証は BigQuery 実接続なしに fake repository で実行できる構成が既にある。
- **Implications**:
  - Django API tests は API client response と fixture body/status の deep equality を採用する。
  - fixture mismatch は scenario ID と field path を出せる helper を再利用する。
  - 実 BigQuery integration は `BIGQUERY_READ_MODEL_INTEGRATION` と credentials が揃う場合だけ実行する。

### CORS と frontend 接続
- **Context**: frontend development origin からの browser request を許可する方法を確認した。
- **Sources Consulted**: `docker-compose.yml`、`frontend/src/features/sessions/api/sessionApi.ts`、`frontend/src/features/sessions/api/sessionApi.types.ts`
- **Findings**:
  - frontend は `http://localhost:51730`、backend は `http://localhost:30000` で動く前提である。
  - frontend request は `Accept: application/json` を付け、sync は `POST` を使う。preflight への明示応答が必要になる可能性がある。
  - 新規 dependency なしでも、Django view / middleware で local development origin に限定した CORS header を返せる。
- **Implications**:
  - 新規 `django-cors-headers` は採用せず、対象 endpoint の local development CORS に限定した軽量実装とする。
  - 許可 origin は settings で明示し、default は `http://localhost:51730` と `http://127.0.0.1:51730` に限定する。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Thin Django views + API service | view は request / response と status を扱い、query / sync coordination は service に寄せる | 既存 presenter / repository 境界を保ち、HTTP 契約を集中管理できる | service が大きくなると sync と read が混ざる | 採用 |
| View 直結 repository 呼び出し | 各 view が repository / presenter / error mapping を直接呼ぶ | 初期実装が少ない | validation、status mapping、sync run lifecycle が重複しやすい | 不採用 |
| DRF 導入 | Django REST Framework で serializer / views を構成する | API 実装機能が豊富 | 新規 dependency と serializer shape drift のリスクが要件に対して大きい | 不採用 |
| django-cors-headers 導入 | CORS middleware を既製 library に任せる | 一般的で設定が簡単 | 現スコープは local development origin 限定で、依存追加の価値が小さい | 今回は不採用 |

## Design Decisions

### Decision: 履歴 API を `history_api` app に分離する
- **Context**: foundation、read model、presenter package と HTTP endpoint 実装の責務を混ぜない必要がある。
- **Alternatives Considered**:
  1. `backend_config.urls` と view 関数だけで実装する。
  2. `history_read_model` app に API view を置く。
  3. `history_api` app を追加する。
- **Selected Approach**: `history_api` app を追加し、URLs、views、request validation、response helpers、service composition、dependency factory を置く。
- **Rationale**: repository は data access、presenter は body shape、`history_api` は HTTP contract という境界が明確になる。
- **Trade-offs**: ファイル数は増えるが、task と review の境界が安定する。
- **Follow-up**: `INSTALLED_APPS` と URL registration のテストを追加する。

### Decision: 保存済み payload を API response の正本にする
- **Context**: BigQuery repository は `summary_payload` / `detail_payload` を返し、presenter contract は保存時の shape を固定している。
- **Alternatives Considered**:
  1. API request ごとに `NormalizedSession` へ戻して Presenter を再実行する。
  2. 保存済み payload をそのまま envelope に入れる。
- **Selected Approach**: list/detail は repository が返す保存済み payload を `data` に入れ、raw opt-in は detail payload 内の保存済み raw fields を返す。
- **Rationale**: 一覧・詳細は read-only で raw files を読まない要件に合い、repository / presenter の既存責務を重複させない。
- **Trade-offs**: 保存済み payload の shape drift は sync / repository 側で検出する必要がある。
- **Follow-up**: fixture tests で API response body と contract fixture を比較する。

### Decision: HTTP validation は API 境界で frontend 契約に合わせる
- **Context**: repository の `SessionListCriteria` validation と frontend の error details contract は同一ではない。
- **Alternatives Considered**:
  1. repository validation result をそのまま返す。
  2. view input validation を追加し、`invalid_session_list_query` envelope を構築する。
- **Selected Approach**: `history_api.query_validation` が `from` / `to` / `limit` / `search` を検証し、`details.field`、`details.reason`、`details.value` を返す。
- **Rationale**: HTTP query 由来の失敗を frontend 契約で安定化し、repository error は backend failure として別 mapping にできる。
- **Trade-offs**: validation ルールの二重化を避けるため、repository validation は最終防衛線として扱う。
- **Follow-up**: invalid datetime、range、limit、search 制御文字、search length の request tests を追加する。

### Decision: CORS は local development 用の明示 header に限定する
- **Context**: この feature は認証・外部公開 hardening を所有しないが、frontend development origin からの接続は必要である。
- **Alternatives Considered**:
  1. `django-cors-headers` を導入する。
  2. 対象 API view / helper で CORS header と OPTIONS response を返す。
- **Selected Approach**: settings の `HISTORY_API_ALLOWED_ORIGINS` を読み、対象 endpoint で `Access-Control-Allow-Origin`、methods、headers を返す。
- **Rationale**: スコープを local development 接続に限定でき、新規 dependency を増やさない。
- **Trade-offs**: 外部公開向けの細かな CORS policy は後続 hardening が必要である。
- **Follow-up**: preflight request の test を追加する。

## Risks & Mitigations
- 保存済み payload と fixture の drift — API fixture tests と presenter / repository contract tests を併用する。
- sync service が reader、row builder、repository、presenter を抱え込み肥大化する — sync coordination と HTTP response mapping を別 component に分ける。
- BigQuery credentials 不在で API tests が不安定になる — fake repository を default test dependency にし、実接続 test は opt-in にする。
- CORS の範囲が広がりすぎる — default allowed origins を local frontend に限定し、認証・外部公開は境界外に明記する。

## References
- `.kiro/specs/api-contract-fixtures/design.md` — Rails 互換 fixture と downstream 利用規約。
- `.kiro/specs/django-backend-foundation/design.md` — Django project、settings、URLconf、quality entrypoint。
- `.kiro/specs/django-presenters-contract/design.md` — presenter body shape と error envelope。
- `.kiro/specs/bigquery-session-repository/design.md` — repository port、fake adapter、BigQuery adapter。
- `frontend/src/features/sessions/api/sessionApi.ts` — frontend request path と error normalization。

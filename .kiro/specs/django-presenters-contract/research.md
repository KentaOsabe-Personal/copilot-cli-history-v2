# Research & Design Decisions

## Summary
- **Feature**: `django-presenters-contract`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 既存の `api-contract-fixtures` は Rails presenter と frontend DTO を正本にした response body fixture を持ち、Django Presenter はこれを read-only expectation として比較する必要がある。
  - Python reader は `NormalizedSession`、`NormalizedEvent`、`ReadIssue` と基礎 projection を提供するが、Rails API と同じ `conversation`、`activity`、`timeline`、`tool_calls.status`、issue envelope まではまだ作らない。
  - 後続の BigQuery repository / Django API は Presenter 出力を利用するが、この spec は repository query、HTTP status routing、request validation を所有しない。

## Research Log

### 既存 contract fixture と frontend DTO
- **Context**: Presenter が生成する JSON body の期待値を確定するため、`.kiro/specs/api-contract-fixtures/fixtures/manifest.json` と代表 response fixture を確認した。
- **Sources Consulted**:
  - `.kiro/specs/api-contract-fixtures/design.md`
  - `.kiro/specs/api-contract-fixtures/fixtures/manifest.json`
  - `.kiro/specs/api-contract-fixtures/fixtures/sessions/index/list_success.response.json`
  - `.kiro/specs/api-contract-fixtures/fixtures/sessions/show/detail_success.response.json`
  - `.kiro/specs/api-contract-fixtures/fixtures/history_sync/*.response.json`
  - `frontend/src/features/sessions/api/sessionApi.types.ts`
- **Findings**:
  - success envelope は `data` と必要な `meta`、error envelope は `error.code`、`error.message`、`error.details` を固定する。
  - 一覧は `meta.count` と `meta.partial_results` を持ち、詳細は `raw_included` と `raw_payload` の null / 実値を `include_raw` で切り替える。
  - frontend DTO は `SessionTimelineToolCall.status` と `SessionActivityEntry.title/summary/raw_available` を期待する。
- **Implications**:
  - Django Presenter の contract tests は manifest の代表 scenario を読み、生成 body と response fixture の `body` を deep equality で比較する。
  - Presenter は HTTP status を返さず、fixture response の `body` だけを生成する境界にする。

### Rails Presenter の責務分解
- **Context**: Django 側でどの Presenter component が必要かを決めるため、Rails の Presenter 実装を確認した。
- **Sources Consulted**:
  - `backend/lib/copilot_history/api/presenters/session_index_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/session_detail_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/history_sync_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/error_presenter.rb`
  - `backend/lib/copilot_history/api/presenters/issue_presenter.rb`
- **Findings**:
  - Rails は `IssuePresenter` を共通利用し、session issue は session scope、event issue は event scope として返す。
  - 詳細 Presenter は event sequence で issue を分配し、session level issue と event level issue を別の位置に置く。
  - sync Presenter は成功 / completed_with_issues を success envelope にし、conflict / root failure / persistence failure は error envelope と必要な `meta` を返す。
- **Implications**:
  - Python 側も Issue / SessionIndex / SessionDetail / HistorySync / Error の小さな Presenter に分ける。
  - `HistorySyncPresenter` は repository/API 実装前でもテストできるよう、Presenter 専用の typed DTO を入力にする。

### Python reader / projection の入力境界
- **Context**: Presenter 入力として使える既存 Python 型と不足分を確認した。
- **Sources Consulted**:
  - `backend/copilot_history/types.py`
  - `backend/copilot_history/projections.py`
  - `.kiro/specs/copilot-history-python-reader/design.md`
  - `backend/tests/copilot_history/test_reader_compatibility.py`
- **Findings**:
  - reader の `NormalizedSession` は session header、events、message snapshots、issues、source paths を保持する。
  - `ConversationProjector` と `ActivityProjector` は基礎 projection を提供するが、Rails detail response と同じ entry shape ではない。
  - `ReadIssue.sequence` は event issue の分配 key として使える。
- **Implications**:
  - Presenter layer は reader の型を変更せず、API response 用 projection mapper を追加する。
  - raw parsing 成否や session source discovery は Presenter のテスト完了条件に含めない。

### Django backend foundation と品質入口
- **Context**: 実装先と検証コマンドを決めるため、Django foundation の構成を確認した。
- **Sources Consulted**:
  - `.kiro/specs/django-backend-foundation/design.md`
  - `backend/pyproject.toml`
  - `backend/tests/copilot_history/test_projections.py`
- **Findings**:
  - backend は Python `>=3.14,<3.15`、Django `>=5.2.8,<5.3`、pytest、ruff、mypy strict を使う。
  - tests は `backend/tests/` 配下に置き、各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを残す。
  - `google-cloud-bigquery` は既に dependency にあるが、Presenter contract には不要である。
- **Implications**:
  - 新規 dependency は追加しない。
  - Contract test は pure Python pytest として実装し、BigQuery / Django request client を使わない。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Rails Presenter の逐語移植 | Ruby Presenter と同じ責務を Python class に分ける | fixture 互換を追いやすい | Python reader projection との差分を隠しやすい | 採用。ただし Python 型境界を明示する |
| fixture first deep equality | Representative fixture の body と Presenter 出力を比較する | contract drift を最短で検出できる | fixture にない field の網羅は別テストが必要 | 採用 |
| JSON Schema / OpenAPI 導入 | schema artifact から検証する | 機械的検証が強い | 現行 spec 範囲を超え、fixture 正本と二重管理になる | 不採用 |
| Django view test で検証 | HTTP 経由で response を比較する | 後続 API に近い | routing / status / repository が混ざる | 後続 `django-history-api` に defer |

## Design Decisions

### Decision: Presenter は response body だけを所有する
- **Context**: 要件は JSON response の形を固定するが、HTTP status routing と request validation は scope 外である。
- **Alternatives Considered**:
  1. Presenter が status と body の tuple を返す。
  2. Presenter が body のみを返し、status は後続 API に任せる。
- **Selected Approach**: Presenter は success / error の response body を返す。`HistorySyncPresenter` も body を返し、status 選択に必要な result kind は API 側へ残す。
- **Rationale**: 1.5、7.5 の境界に合い、Django view / repository なしで contract tests を実行できる。
- **Trade-offs**: 後続 API で status mapping のテストが別途必要になる。
- **Follow-up**: `django-history-api` で manifest の `status` と Presenter body を組み合わせた request tests を追加する。

### Decision: Sync input は Presenter 専用 DTO にする
- **Context**: Python 側には Rails の `SyncResult` 相当がまだない。
- **Alternatives Considered**:
  1. この spec で sync service / repository result を作る。
  2. Presenter contract 用の typed DTO を作り、後続 repository/API が変換する。
- **Selected Approach**: `HistorySyncRunPresenterInput`、`HistorySyncCountsInput`、`HistorySyncPresentationResult` を `copilot_history.api.types` に置く。
- **Rationale**: sync response shape を固定しつつ、repository lifecycle や persistence failure 判定をこの spec に取り込まない。
- **Trade-offs**: 後続 repository/API 実装で DTO 変換の境界テストが必要になる。
- **Follow-up**: `bigquery-session-repository` と `django-history-api` の tasks で DTO 変換を検証する。

### Decision: API response 用 projection mapper を Presenter 層に置く
- **Context**: Python reader の projection は基礎情報を返すが、frontend DTO は Rails API shape を期待する。
- **Alternatives Considered**:
  1. reader projection を Rails API shape へ拡張する。
  2. Presenter 層で `NormalizedSession` と基礎 projection から API shape を組み立てる。
- **Selected Approach**: Presenter 層に `SessionResponseProjector` を置き、conversation / activity / timeline の API shape を作る。
- **Rationale**: reader は raw format 非依存の normalized contract に保ち、HTTP response 依存を逆流させない。
- **Trade-offs**: projection 名が reader 側と Presenter 側で近くなるため、file responsibility を明確にする必要がある。
- **Follow-up**: tasks では reader の `projections.py` を変更しない boundary を明記する。

### Decision: 新規 dependency は追加しない
- **Context**: deep equality と fixture loading は Python 標準 library と pytest で足りる。
- **Alternatives Considered**:
  1. JSON diff library を追加する。
  2. pytest assertion rewriting と小さな field path helper を使う。
- **Selected Approach**: 標準 `json` と pytest assertion、必要なら contract test helper で field path を表示する。
- **Rationale**: 依存を増やさず、Django / BigQuery の移行境界を広げない。
- **Trade-offs**: 大きな差分の可読性は専用 diff library より弱い。
- **Follow-up**: fixture 差分が読みにくい場合だけ、後続で helper を改善する。

## Risks & Mitigations
- Python reader projection と Rails response shape の差分を混同する — Presenter 層に API response mapper を置き、reader 型を変更しない。
- fixture の一部 scenario だけで互換漏れが起きる — manifest の一覧、詳細、raw、sync、error の代表 response を contract tests に含める。
- sync DTO が後続 repository とずれる — DTO は sync response body に必要な field だけを持ち、repository lifecycle は後続 spec で再検証する。
- test data construction が肥大化する — fixture scenario ごとに最小の typed builder を用意し、raw reader の fixture 読取を Presenter test の前提にしない。

## References
- `.kiro/specs/api-contract-fixtures/design.md` — fixture 正本と downstream 利用境界。
- `.kiro/specs/api-contract-fixtures/fixtures/manifest.json` — contract test 対象 scenario。
- `.kiro/specs/copilot-history-python-reader/design.md` — `NormalizedSession` 入力境界。
- `.kiro/specs/django-backend-foundation/design.md` — Django / pytest / mypy strict の実装基盤。
- `frontend/src/features/sessions/api/sessionApi.types.ts` — frontend DTO contract。

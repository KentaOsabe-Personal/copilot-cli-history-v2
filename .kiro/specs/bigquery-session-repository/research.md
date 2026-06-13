# Research & Design Decisions

## Summary
- **Feature**: `bigquery-session-repository`
- **Discovery Scope**: Complex Integration
- **Key Findings**:
  - 既存 Rails query は表示日時を `updated_at_source` 優先、欠落時は `created_at_source` fallback として扱い、保存済み `summary_payload` / `detail_payload` を再構築せず返している。
  - `bigquery-read-model-schema` は `source_partition_date` 必須、`summary_payload` / `detail_payload` JSON object、`history_sync_runs.running_lock_key`、fake repository の保存契約を提供済みであり、この仕様はその上に query / write repository 契約を重ねる。
  - BigQuery では parameterized query、partition pruning、dry run、`maximum_bytes_billed`、partitioned table に対する `MERGE` が標準機能として利用できるため、cost guardrail と upsert は platform native capability を採用する。

## Research Log

### 既存 session query / sync 契約
- **Context**: BigQuery repository が Rails / MySQL 版の一覧・詳細・同期保存契約を崩さないため、既存 query service と sync service を確認した。
- **Sources Consulted**:
  - `backend/lib/copilot_history/api/session_index_query.rb`
  - `backend/lib/copilot_history/api/session_detail_query.rb`
  - `backend/lib/copilot_history/sync/history_sync_service.rb`
  - `backend/spec/lib/copilot_history/api/session_index_query_spec.rb`
- **Findings**:
  - 一覧は `updated_at_source` がある row を優先し、欠落時だけ `created_at_source` を表示日時に使う。どちらもない row は候補外である。
  - 並び順は表示日時降順、同一表示日時では `session_id` 昇順で安定化し、limit は並び替え後に適用する。
  - 検索は `search_text` または `cwd` に対する literal match であり、`repository` 単独一致は対象外である。
  - 詳細取得は `session_id` lookup で保存済み `detail_payload` を返し、raw files を読まない。
  - 同期保存は `session_id` を identity とし、source fingerprint と search projection version が現行なら skip、新規なら inserted、既存差分なら updated として集計する。
- **Implications**:
  - BigQuery list query は API payload を BigQuery SQL 内で再構築せず、candidate selection 後に保存済み `summary_payload` を返す。
  - `search_text` と `cwd` の wildcard は user input として escape し、parameterized query で扱う。
  - sync write は `session_id` identity と fingerprint comparison を repository 契約に含める。

### BigQuery read model schema と fake 契約
- **Context**: 後続 repository が依存できる schema / fake の境界を確認した。
- **Sources Consulted**:
  - `.kiro/specs/bigquery-read-model-schema/design.md`
  - `backend/history_read_model/bigquery_schema.py`
  - `backend/history_read_model/fake_repository.py`
  - `backend/tests/history_read_model/test_fake_repository_contract.py`
- **Findings**:
  - `copilot_sessions` は `source_partition_date` による required partition key、`session_id` cluster、source metadata、counts、degraded、JSON payload、`search_text` / `search_text_version` を持つ。
  - `history_sync_runs` は `sync_run_id`、status lifecycle、count fields、failure / degradation summary、`running_lock_key` を持つ。
  - fake repository は BigQuery client fake ではなく、required fields、enum、非負 count、JSON object payload、sync lifecycle を検証する保存契約 fake として実装済みである。
- **Implications**:
  - この仕様では schema 定義を再作成せず、`history_read_model.bigquery_schema` と row dataclass を利用する。
  - repository fake は既存 fake を query / write contract まで拡張するか、同じ row contract を使う repository fake adapter として提供する。
  - `source_partition_date` は cost guardrail 用の partition filter、`updated_at_source` / `created_at_source` は要件上の表示日時 filter / order として役割を分ける。

### Django presenter / API payload 境界
- **Context**: repository が presenter payload shape を所有しないことを確認した。
- **Sources Consulted**:
  - `.kiro/specs/django-presenters-contract/design.md`
  - `backend/copilot_history/api/types.py`
  - `backend/copilot_history/api/response_projection.py`
  - `backend/tests/copilot_history/test_api_presenter_contract.py`
- **Findings**:
  - Python presenter は response body の shape を所有し、repository / Django view / BigQuery client を境界外にしている。
  - `summary_payload` / `detail_payload` は presenter-compatible JSON object として保存される。
  - sync response body に必要な run / counts DTO は presenter 側にあるが、永続化 row の lifecycle と identity は repository 側で扱う必要がある。
- **Implications**:
  - repository interface は payload を `Mapping[str, object]` として透過的に返し、payload 内部 field の再定義をしない。
  - Django API は後続 spec で repository result を presenter / HTTP status に写す。repository は HTTP error code を返さない。

### BigQuery query / cost guardrail / DML
- **Context**: cost guardrail と secure query construction を BigQuery 標準機能で設計できるか確認した。
- **Sources Consulted**:
  - [Running parameterized queries](https://docs.cloud.google.com/bigquery/docs/parameterized-queries)
  - [Introduction to partitioned tables](https://docs.cloud.google.com/bigquery/docs/partitioned-tables)
  - [Run a query](https://docs.cloud.google.com/bigquery/docs/running-queries)
  - [Estimate and control costs](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)
  - [Updating partitioned table data using DML](https://cloud.google.com/bigquery/docs/using-dml-with-partitioned-tables)
  - [Data manipulation language statements in GoogleSQL](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax)
- **Findings**:
  - BigQuery named parameters can bind user values in GoogleSQL and avoid interpolating search / date / limit values into SQL.
  - Partitioned tables can prune scanned partitions when queries include qualifying filters on the partitioning column.
  - Dry run can estimate query processing without executing data changes for query jobs.
  - `maximum_bytes_billed` prevents a query job from succeeding when the estimated bytes exceed the caller-provided cap.
  - `MERGE` combines insert/update operations atomically; partitioned-table DML should include partition filters in source subqueries, search conditions, or merge conditions to support pruning.
- **Implications**:
  - List queries must require an explicit date range and translate it to `source_partition_date BETWEEN @from_date AND @to_date`; missing range is a repository validation error.
  - BigQuery adapter will use `QueryJobConfig` with named parameters, dry-run mode, and `maximum_bytes_billed` when configured.
  - Sync write uses a temporary or scoped staging table plus `MERGE` for `copilot_sessions`; dry run validates planned SQL / row contract and does not mutate BigQuery.
  - Detail lookup by `session_id` may not benefit from the partition filter; the design keeps detail lookup cost controlled by clustering and `maximum_bytes_billed`, not by inventing a date precondition absent from requirements.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Django ORM repository | BigQuery を Django model 相当に扱う | Django 利用者には馴染みやすい | BigQuery を通常 DB とする誤解を生み、schema spec の境界に反する | 不採用 |
| Port + BigQuery adapter + fake adapter | typed repository interface を定義し、BigQuery と fake を同じ契約で検証する | API / sync が BigQuery 詳細から分離され、unit test が安定する | adapter と contract test を新規実装する必要がある | 採用 |
| BigQuery SQL を view / sync service に直書き | 実装ファイル数が少ない | SQL、cost guardrail、error mapping が呼び出し側に漏れる | 不採用 |
| Search Index / semantic search 採用 | 大規模検索に強い | 要件の検索対象と初期 scope を超える | 初期 scope 外 |

## Design Decisions

### Decision: Repository port を API / sync の共有境界にする
- **Context**: 一覧、詳細、同期保存、sync run 保存を同じ read model 契約として提供する必要がある。
- **Alternatives Considered**:
  1. API query class と sync writer を別々に作る。
  2. `SessionReadModelRepository` port に read / write / sync run 契約を集約し、実装を adapter で切る。
- **Selected Approach**: `history_read_model.repository` に typed port、result dataclass、error union を置き、`BigQuerySessionRepository` と fake adapter が同じ interface を満たす。
- **Rationale**: BigQuery SQL と cost guardrail を repository 内に閉じ、Django API / sync service は結果型だけに依存できる。
- **Trade-offs**: port は read と write の両方を持つため大きめになるが、read model 境界としては要件上同一である。
- **Follow-up**: implementation task では interface、fake、BigQuery adapter、contract tests の順に構築する。

### Decision: List query は partition filter と display time filter を分離する
- **Context**: 要件は display time を `updated_at_source` 優先・`created_at_source` fallback とする一方、BigQuery schema は `source_partition_date` を partition key とする。
- **Alternatives Considered**:
  1. `source_partition_date` だけで日付一致を判定する。
  2. `COALESCE(updated_at_source, created_at_source)` だけで query する。
  3. `source_partition_date` で scan 範囲を絞り、同じ query 内で display time を計算して要件上の range / order を適用する。
- **Selected Approach**: list query は `source_partition_date BETWEEN @from_date AND @to_date` を必須にし、candidate selection では `CASE WHEN updated_at_source IS NOT NULL THEN updated_at_source ELSE created_at_source END` 相当の display time を使う。両方 null の row は除外する。
- **Rationale**: cost guardrail と表示契約を同時に満たせる。
- **Trade-offs**: sync write 側の `source_partition_date` 算出が表示日時とずれると row が候補外になる可能性があるため、contract tests に partition/date consistency を含める。
- **Follow-up**: schema 側の partition derivation 変更時はこの spec を再検証する。

### Decision: BigQuery native dry run / maximum bytes billed / parameterized query を採用する
- **Context**: user input search と cost 上限を repository 内で扱う必要がある。
- **Alternatives Considered**:
  1. SQL string escape を自前実装する。
  2. BigQuery named parameters と `QueryJobConfig` を利用する。
- **Selected Approach**: すべての user supplied criteria は named parameters にし、dry run と `maximum_bytes_billed` は `RepositoryExecutionOptions` で list / detail / write に伝播する。
- **Rationale**: platform 標準機能で SQL injection risk と scan cost を抑える。
- **Trade-offs**: dry run の戻り値は実 data result ではなく plan / validation result になるため、result union に dry-run branch が必要になる。
- **Follow-up**: implementation では query text と parameters を unit test で検証し、実接続 validation は opt-in にする。

### Decision: Sync write は staging + MERGE を repository 内部 batch 契約にする
- **Context**: BigQuery table で insert / update / skip を session_id 単位に集計し、重複 row を避ける必要がある。
- **Alternatives Considered**:
  1. `insert_rows_json` の append のみで保存する。
  2. 既存 row を個別 SELECT / UPDATE する。
  3. 保存候補を staging table に置き、target table へ `MERGE` する。
- **Selected Approach**: row contract validation 後、staging rows と target `copilot_sessions` を `session_id` で MERGE する。fingerprint と search version が一致する row は skip 集計にし、workspace only は staging へ入れない。
- **Rationale**: BigQuery の atomic DML に寄せ、repository が idempotent write 境界を持てる。
- **Trade-offs**: staging table lifecycle と cleanup が必要になる。初期設計では background job 化や長期運用 policy は含めない。
- **Follow-up**: opt-in integration test で MERGE の代表挙動を確認する。

## Synthesis Outcomes
- **Generalization**: list / detail / sync write / sync run write はすべて「read model row contract を扱う repository operation」として扱う。payload shape は repository の外に置き、row identity・filter・cost・lifecycle を repository の責務に集約する。
- **Build vs Adopt**: BigQuery query execution、dry run、maximum bytes billed、parameterized query、DML MERGE は BigQuery native 機能を採用する。payload presenter、schema definition、fake contract は既存プロジェクト実装を再利用する。
- **Simplification**: Django ORM adapter、Search Index、semantic search、background job lock manager、production GCP operation layerは追加しない。sync conflict は `history_sync_runs.running_lock_key` の repository lookup に閉じる。

## Risks & Mitigations
- List query が partition filter なしで実行される — repository input validation で date range 欠落を `missing_date_range` error にし、SQL builder test で `source_partition_date` predicate を検証する。
- Display time と partition date が drift する — fake / contract tests に updated fallback、created fallback、timestamp 欠落除外、partition range の代表ケースを入れる。
- BigQuery error が呼び出し側で分類できない — credentials、permission、schema mismatch、cost limit、query failure を `RepositoryError.kind` で分類する。
- Dry run が write mutation を起こす — execution options を repository 全 operation に通し、dry run branch は staging / MERGE 実行を禁止する。
- Fake と BigQuery adapter の挙動差 — shared contract tests を fake と BigQuery adapter SQL validation / opt-in integration に適用する。

## References
- [BigQuery parameterized queries](https://docs.cloud.google.com/bigquery/docs/parameterized-queries) — user input を named parameter として扱う根拠。
- [BigQuery partitioned tables](https://docs.cloud.google.com/bigquery/docs/partitioned-tables) — partition pruning と cost control の根拠。
- [BigQuery running queries](https://docs.cloud.google.com/bigquery/docs/running-queries) — dry run と query job 実行の根拠。
- [BigQuery cost best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs) — dry run と maximum bytes billed の根拠。
- [BigQuery DML with partitioned tables](https://cloud.google.com/bigquery/docs/using-dml-with-partitioned-tables) — partitioned table に対する DML / MERGE pruning の根拠。
- [BigQuery DML syntax](https://cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax) — MERGE semantics の根拠。

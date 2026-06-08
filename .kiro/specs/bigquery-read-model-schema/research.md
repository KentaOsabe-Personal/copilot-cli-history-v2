# Research & Design Decisions

## Summary
- **Feature**: `bigquery-read-model-schema`
- **Discovery Scope**: Complex Integration
- **Key Findings**:
  - 既存 Rails / MySQL read model は `copilot_sessions` と `history_sync_runs` の保存契約を既に持つため、BigQuery 版は API payload の再定義ではなく datastore contract の移植として扱う。
  - BigQuery は `JSON` 型、TIMESTAMP column partition、clustering、`INFORMATION_SCHEMA` metadata 照合を標準機能として提供するため、schema 初期化は Django migration ではなく明示 SQL と Python 初期化入口で管理する。
  - 通常 unit test と Django settings import は BigQuery 実接続を要求せず、schema-only validation と fake repository contract で後続 repository / API spec を進められるようにする。

## Research Log

### 既存 Rails read model 契約
- **Context**: BigQuery schema が現行 API contract と raw file 正本の原則を壊さないため、Rails / MySQL 側の保存項目と validation を確認した。
- **Sources Consulted**:
  - `backend/db/schema.rb`
  - `backend/app/models/copilot_session.rb`
  - `backend/app/models/history_sync_run.rb`
  - `backend/lib/copilot_history/persistence/session_record_builder.rb`
  - `backend/lib/copilot_history/sync/history_sync_service.rb`
  - `backend/spec/db/history_read_model_schema_spec.rb`
- **Findings**:
  - `copilot_sessions.session_id` は一意で、source format / state、source timestamps、workspace metadata、counts、degraded flag、preview、source paths、source fingerprint、summary/detail payload、search text、indexed timestamp を保持する。
  - `history_sync_runs` は `running/succeeded/failed/completed_with_issues`、started / finished timestamps、count fields、failure / degradation summary、`running_lock_key` を保持する。
  - `summary_payload` と `detail_payload` は presenter が生成した API payload を JSON object として保存し、後続 API は payload の shape を再構築せず読み出せる前提である。
- **Implications**:
  - BigQuery schema は Rails column contract を起点にしつつ、`created_at` / `updated_at` の Rails 管理列よりも BigQuery read model として意味を持つ source / indexed / sync timestamps を優先する。
  - BigQuery 側でも payload columns は JSON object contract を保ち、presenter payload の再定義をこの spec に含めない。

### Django foundation と移行ロードマップ
- **Context**: 新規ファイル配置と依存方向が既存 Django foundation と roadmap に沿うか確認した。
- **Sources Consulted**:
  - `.kiro/specs/django-backend-foundation/design.md`
  - `.kiro/steering/roadmap.md`
  - `backend/pyproject.toml`
  - `backend/backend_config/settings.py`
  - `backend/tests/test_django_project_foundation.py`
- **Findings**:
  - Django foundation は BigQuery を通常 DB / Django ORM 永続化先にしないことを明示している。
  - Roadmap は BigQuery schema を `bigquery-session-repository` より前に置き、query / detail / staging + MERGE を後続 spec に残している。
  - 現在の backend package は `backend_config` と `health` のみを Python package として検出している。
- **Implications**:
  - 新規 Python module は `history_read_model` package として追加し、`pyproject.toml` の package discovery を更新する。
  - settings は BigQuery client を import せず、環境値の読み取り関数だけを置く。実接続は opt-in management command に閉じる。

### BigQuery schema / metadata 機能
- **Context**: JSON payload、partition / clustering、schema 照合を BigQuery 標準機能で実現できるか確認した。
- **Sources Consulted**:
  - [Working with JSON data in GoogleSQL](https://docs.cloud.google.com/bigquery/docs/json-data)
  - [Creating partitioned tables](https://docs.cloud.google.com/bigquery/docs/creating-partitioned-tables)
  - [Introduction to clustered tables](https://docs.cloud.google.com/bigquery/docs/clustered-tables)
  - [Introduction to INFORMATION_SCHEMA](https://docs.cloud.google.com/bigquery/docs/information-schema-intro)
  - [TABLE_OPTIONS view](https://docs.cloud.google.com/bigquery/docs/information-schema-table-options)
  - [COLUMNS view](https://docs.cloud.google.com/bigquery/docs/information-schema-columns)
- **Findings**:
  - BigQuery は `JSON` 型で semi-structured JSON を保存・照会できるが、JSON columns は partition / clustering key にできない。
  - TIMESTAMP column は `TIMESTAMP_TRUNC(column, DAY)` による time-unit partition を作成できる。
  - Clustering は clustering columns に対する filter で block pruning を支援し、partitioned table と組み合わせられる。
  - `INFORMATION_SCHEMA` は read-only metadata view で、`COLUMNS` と `TABLE_OPTIONS` から column type / nullability / options を検証できる。
- **Implications**:
  - `summary_payload` / `detail_payload` / `source_paths` / `source_fingerprint` は `JSON` 型にするが、lookup / filter 用 column は scalar として別に保持する。
  - `copilot_sessions` は `updated_at_source` を daily partition の基準にし、null source timestamp を避けるため `source_partition_date` を生成済み `DATE` として保持する。
  - schema validation は `INFORMATION_SCHEMA.COLUMNS` と `TABLE_OPTIONS` を使い、実 dataset があるときだけ opt-in で実行する。

### Python BigQuery client dependency
- **Context**: 実接続 command と opt-in integration validation に必要な Python dependency を確認した。
- **Sources Consulted**:
  - [google-cloud-bigquery on PyPI](https://pypi.org/project/google-cloud-bigquery/)
- **Findings**:
  - `google-cloud-bigquery` は 2026-03-30 時点で 3.41.0 が公開されている。
  - 既存 backend は Python `>=3.14,<3.15` を前提にしているため、implementation 時は Python 3.14 環境で dependency resolution と import を検証する必要がある。
- **Implications**:
  - `backend/pyproject.toml` には `google-cloud-bigquery>=3.41,<4` を追加する設計にする。
  - dependency import は BigQuery 実接続入口に限定し、unit test は schema definition / fake client で通せる構成にする。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Django migration 管理 | BigQuery schema を Django migration 相当に扱う | Django 既存概念に近い | BigQuery を通常 DB として扱う誤解を生む。roadmap の制約に反する | 不採用 |
| SQL + schema definition + management command | Python module に schema contract と DDL を置き、明示 command で作成 / 照合する | BigQuery read model 境界が明確。実接続 opt-in にできる | command / validation を新規実装する必要がある | 採用 |
| Terraform / IaC 管理 | Dataset / table を IaC で管理する | 本番運用に強い | 初期 scope の高度な GCP 運用設計を超える | 初期 scope 外 |
| Query repository と同時実装 | schema、query、upsert を同じ spec で実装する | 一気に動作確認できる | boundary が大きすぎ、後続 spec の責務を吸収する | 不採用 |

## Design Decisions

### Decision: BigQuery schema は Django migration ではなく明示 schema initializer で管理する
- **Context**: 要件 3.4 と roadmap は BigQuery を Django ORM 永続化先として扱わないことを求めている。
- **Alternatives Considered**:
  1. Django migration に BigQuery DDL を混ぜる。
  2. Python schema module と management command で BigQuery DDL を提示・実行する。
- **Selected Approach**: `history_read_model.bigquery_schema` に table contract と DDL を定義し、`init_bigquery_read_model` management command が dry-run 表示、環境 validation、create / compare を担当する。
- **Rationale**: datastore contract と runtime DB を分離でき、unit test は実接続なしで schema contract を検証できる。
- **Trade-offs**: Django migration の履歴管理には乗らないため、schema version は module 定数と docs / tests で管理する。
- **Follow-up**: implementation で command name、dry-run default、差分出力形式を固定する。

### Decision: Payload は JSON 型、検索・絞り込みは scalar columns で保持する
- **Context**: presenter payload の shape は後続 `django-presenters-contract` に属するが、BigQuery schema は payload を失わず保存する必要がある。
- **Alternatives Considered**:
  1. payload 全体を STRING として保存する。
  2. payload を BigQuery `JSON` 型として保存し、lookup 用 metadata は scalar columns に分離する。
  3. payload を nested STRUCT として完全分解する。
- **Selected Approach**: `summary_payload` / `detail_payload` / `source_paths` / `source_fingerprint` は `JSON`、session id / repository / branch / source state / counts / timestamps / search text は scalar columns として定義する。
- **Rationale**: JSON shape を失わず、BigQuery の partition / clustering に使う項目は JSON に依存しない。
- **Trade-offs**: JSON payload 内の高度な分析や JSON path indexing は初期 scope 外に残る。
- **Follow-up**: presenter payload version が必要になった場合は downstream revalidation trigger とする。

### Decision: `source_partition_date` を partition key として持つ
- **Context**: 日付範囲取得は source timestamp を前提にするが、source timestamp は現行 schema 上 nullable である。
- **Alternatives Considered**:
  1. `updated_at_source` だけで partition する。
  2. ingestion time partition を使う。
  3. `source_partition_date` を required `DATE` として計算し、`updated_at_source` がない場合は `created_at_source`、それもない場合は `indexed_at` 由来にする。
- **Selected Approach**: `source_partition_date DATE NOT NULL` を追加し、`copilot_sessions` を `PARTITION BY source_partition_date` にする。`updated_at_source` は list query の主要 order / range column として残す。
- **Rationale**: null timestamp を含む degraded / legacy data でも partition filter を強制できる。
- **Trade-offs**: repository / sync 側は partition date の算出責任を持つ必要がある。
- **Follow-up**: 後続 repository spec は list query で `source_partition_date` filter を必須条件として扱う。

### Decision: fake repository は BigQuery client fake ではなく保存契約 fake とする
- **Context**: 後続 API / repository unit test は実 BigQuery dataset なしで主要 contract を検証する必要がある。
- **Alternatives Considered**:
  1. `google-cloud-bigquery` client を深く mock する。
  2. 保存レコード contract を検証する in-memory fake repository を定義する。
- **Selected Approach**: fake repository は `CopilotSessionRow` と `HistorySyncRunRow` の required fields、enum、counts、JSON object payload、search text version を検証する。
- **Rationale**: BigQuery API の実装詳細ではなく、後続 consumers が依存する datastore contract を検証できる。
- **Trade-offs**: BigQuery SQL syntax や job behavior は opt-in integration validation に残る。
- **Follow-up**: `bigquery-session-repository` はこの fake contract と実 adapter の parity tests を追加する。

## Risks & Mitigations
- BigQuery 実接続が unit test に漏れる — settings import で client を作らず、integration validation は env flag 必須にする。
- JSON payload と scalar metadata が diverge する — fake repository と schema validation で required scalar / JSON object contract を検証し、payload shape の再定義は後続 presenter spec へ戻す。
- Partition key と query filter が downstream でずれる — `source_partition_date` を design と validation の required column にし、後続 repository の revalidation trigger にする。
- `google-cloud-bigquery` の Python 3.14 対応が implementation 時に崩れる — dependency resolution / import test を task に含める。

## References
- [BigQuery JSON data](https://docs.cloud.google.com/bigquery/docs/json-data) — JSON columns と JSON 型制約。
- [BigQuery partitioned tables](https://docs.cloud.google.com/bigquery/docs/creating-partitioned-tables) — `PARTITION BY` と partition filter option。
- [BigQuery clustered tables](https://docs.cloud.google.com/bigquery/docs/clustered-tables) — clustering と block pruning。
- [BigQuery INFORMATION_SCHEMA introduction](https://docs.cloud.google.com/bigquery/docs/information-schema-intro) — metadata view の性質。
- [BigQuery TABLE_OPTIONS view](https://docs.cloud.google.com/bigquery/docs/information-schema-table-options) — table options 照合。
- [BigQuery COLUMNS view](https://docs.cloud.google.com/bigquery/docs/information-schema-columns) — column metadata 照合。
- [google-cloud-bigquery PyPI](https://pypi.org/project/google-cloud-bigquery/) — Python client dependency。

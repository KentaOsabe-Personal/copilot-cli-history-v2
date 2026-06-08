# 調査・設計判断

## Summary
- **Feature**: `copilot-history-python-reader`
- **Discovery Scope**: Extension
- **Key Findings**:
  - Rails 側 `backend/lib/copilot_history/` には root 解決、source 列挙、current / legacy reader、event normalizer、conversation / activity projector、read issue 型が揃っており、Python 移植の互換基準として使える。
  - Django backend 基盤は Python `>=3.14,<3.15`、Django `>=5.2.8,<5.3`、pytest、ruff、mypy strict を前提にしている。reader は dataclass と型 alias を中心に実装しつつ、`workspace.yaml` 読取だけは `PyYAML.safe_load` を使う。
  - BigQuery read model は `source_format`、`source_state`、counts、summary/detail/search projection を後続入力として期待しているが、この spec は保存 schema や HTTP shape を所有しない。

## Research Log

### Rails reader contract の移植範囲
- **Context**: Python reader が current / legacy の normalized session と issue 情報を Rails 互換で返す必要がある。
- **Sources Consulted**: `backend/lib/copilot_history/session_catalog_reader.rb`, `session_source_catalog.rb`, `current_session_reader.rb`, `legacy_session_reader.rb`, `event_normalizer.rb`, `types/*.rb`, `projections/*.rb`
- **Findings**:
  - 公開入口は root failure と success を分ける `SessionCatalogReader` で、source 列挙後の session 単位の parse 問題は `ReadIssue` として保持される。
  - current は `session-state/<session-id>/workspace.yaml` と `events.jsonl` を同一 session として扱い、legacy は `history-session-state/*.json` の `timeline` と `chatMessages` を読み分ける。
  - normalized session は `session_id`、`source_format`、`source_state`、work context、timestamps、`selected_model`、events、message snapshots、issues、source paths を保持する。
  - conversation / activity / search projection は normalized session から派生するが、HTTP presenter の payload shape とは別境界である。
- **Implications**:
  - Python 側も `SessionCatalogReader` 相当の facade を公開し、root failure と degraded session を union type で分ける。
  - Rails の class 名を直訳するより、Python package 内の module 分割で同じ責務境界を維持する。

### Python backend 基盤と品質制約
- **Context**: 移植先の実行環境とテスト入口を確認する必要がある。
- **Sources Consulted**: `backend/pyproject.toml`, `.kiro/specs/django-backend-foundation/design.md`, `backend/history_read_model/*.py`, `backend/tests/history_read_model/*.py`
- **Findings**:
  - Python package discovery は `backend/pyproject.toml` の `[tool.setuptools.packages.find]` に明示されている。
  - mypy は strict で、既存 Python code は `dataclass(frozen=True)`、`Literal`、明示的な `Mapping` / `Sequence` を使う。
  - テストは `backend/tests/` 配下に置き、各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く規約が既存テストでも適用されている。
- **Implications**:
  - 新規 package `backend/copilot_history/` を `pyproject.toml` の package discovery に追加する。
  - 型は dataclass と `Literal` で定義し、動的 payload は境界で `Mapping[str, object]` として検証する。
  - YAML 解析は current `workspace.yaml` の利用 field に限定し、`PyYAML.safe_load` 以外の object 復元 API は使わない。

### `workspace.yaml` 解析依存
- **Context**: current reader は `workspace.yaml` から session id、cwd、git context、timestamps を読む必要がある。標準 library には YAML parser がない。
- **Sources Consulted**: `backend/lib/copilot_history/current_session_reader.rb`, `backend/pyproject.toml`, PyPI `PyYAML` project page
- **Findings**:
  - Rails 実装は `Psych.safe_load` で `workspace.yaml` を読み、payload が mapping でない場合は parse failure issue にする。
  - PyPI の `PyYAML` は 6.0.3 が公開済みで、Python 3.14 向け wheel も提供されている。
  - YAML を手製 parser で扱うと quoted string、timestamp、nested mapping の扱いが不安定になり、Rails fixture との parity を落としやすい。
- **Implications**:
  - `backend/pyproject.toml` の runtime dependencies に `PyYAML>=6.0.3,<7` を追加する。
  - current reader は `yaml.safe_load` のみを使い、読み取った payload が `Mapping` であることを境界で検証する。
  - `test_current_reader.py` に valid YAML、invalid YAML、non-mapping YAML の fixture を置く。

### Rails 互換ルールの固定
- **Context**: Python reader は Rails 版 reader / normalizer / projection と同等の入力データを downstream へ渡す必要がある。
- **Sources Consulted**: `backend/lib/copilot_history/current_session_reader.rb`, `backend/lib/copilot_history/event_normalizer.rb`, `backend/lib/copilot_history/projections/conversation_projector.rb`
- **Findings**:
  - selected model は `session.shutdown data.currentModel`、`tool.execution_complete data.model`、`assistant.usage data.model`、top-level `model` の順に優先され、同優先度では後の event が勝つ。
  - current event は `user.message` / `assistant.message` / `system.message`、detail 系 regex、legacy-compatible message type、unknown に分類される。
  - tool call arguments は sensitive key を redaction し、preview は 240 文字で切り詰める。
- **Implications**:
  - `design.md` に selected model priority、event mapping、tool call compatibility を表として固定する。
  - テストは Rails fixture の期待値に加え、priority tie と tool call redaction を明示的に検証する。

### Downstream contract との境界
- **Context**: 後続 spec が reader の出力を BigQuery 保存、Django presenter、API へ渡す。
- **Sources Consulted**: `.kiro/specs/bigquery-read-model-schema/design.md`, `.kiro/specs/api-contract-fixtures/contract.md`, `backend/history_read_model/bigquery_schema.py`, `backend/history_read_model/fake_repository.py`
- **Findings**:
  - BigQuery schema は `source_format` に `current | legacy`、`source_state` に `complete | workspace_only | degraded` を期待する。
  - `summary_payload` / `detail_payload` は presenter 互換 payload として保存されるが、reader はその JSON shape を定義しない。
  - search text は conversation、preview、issue 由来の基礎情報を使うが、DB query や ranking は repository / API 側の責務である。
- **Implications**:
  - Python reader は `ConversationProjection`、`ActivityProjection`、`SearchTextSource` までを返せる pure domain service とし、保存 row や HTTP response は生成しない。
  - downstream の再検証トリガーとして normalized data model と issue code の変更を明示する。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Rails 直訳 | Ruby class を Python class へほぼ 1:1 で移す | 差分比較が容易 | Python の型・module 構成に合わない部分が残る | 採用しないが互換基準として参照する |
| Reader pipeline | root resolver、source catalog、format reader、normalizer、projector を分ける | 既存境界を維持しつつ Python 型で検証しやすい | module 数は増える | 採用 |
| Presenter 一体型 | reader が API summary/detail まで作る | 後続 API がすぐ使える | この spec の境界を越え、payload 変更時の責務が曖昧になる | 不採用 |

## Design Decisions

### Decision: Reader pipeline を Python package として移植する
- **Context**: current / legacy 差分、root failure、session degraded、projection を分けて後続 spec へ渡す必要がある。
- **Alternatives Considered**:
  1. Rails class の完全直訳。互換確認は容易だが Python の型安全性と module 分割に合わない。
  2. presenter / repository まで含む一体 service。後続開発は速いが境界を越える。
  3. reader pipeline。責務を分け、normalized contract を公開する。
- **Selected Approach**: `copilot_history` package に types、errors、root resolver、source catalog、current reader、legacy reader、event normalizer、conversation/activity/search projector を置く。
- **Rationale**: 既存 Rails の責務境界を保ち、Django / BigQuery / HTTP へ依存しない reader を実装できる。
- **Trade-offs**: module 数は増えるが、テスト境界と task boundary が明確になる。
- **Follow-up**: Rails fixture と Python fixture の代表差分をテストで固定する。

### Decision: Public contract は dataclass と Literal union で固定する
- **Context**: mypy strict と downstream contract の両方を満たす必要がある。
- **Alternatives Considered**:
  1. dict を直接返す。実装は短いが contract drift を検出しにくい。
  2. Pydantic 等の外部 validation library を追加する。境界 validation は強いが依存追加が重い。
  3. 標準 dataclass、`Literal`、明示 validation helper を使う。
- **Selected Approach**: `types.py` に frozen dataclass と `Literal` 型を置き、入力境界で value を検証する。
- **Rationale**: 既存 Python code の style に合い、外部依存なしで strict typing と immutable value を維持できる。
- **Trade-offs**: runtime validation は必要箇所に手実装する。
- **Follow-up**: 不正 enum、負数 sequence、payload 型違反を unit test で固定する。

### Decision: Session counts と degraded は derived property として公開する
- **Context**: Requirement 4.4 は normalized session に counts と degraded state を含めることを求める。一方で `events`、`message_snapshots`、`issues` と重複して count field を保持すると不整合が起きる。
- **Alternatives Considered**:
  1. `event_count`、`issue_count` を constructor field として持つ。downstream 参照は簡単だが、tuple 長との drift が起きる。
  2. counts を downstream に毎回算出させる。reader contract が薄くなり、後続 spec 間で算出規則が分散する。
  3. `NormalizedSession` の read-only property として counts と `degraded` を公開する。
- **Selected Approach**: `event_count`、`message_snapshot_count`、`issue_count`、`degraded` を public property として固定する。
- **Rationale**: downstream は typed field として参照でき、reader 内では single source of truth を保てる。
- **Trade-offs**: property contract を型テストで守る必要がある。
- **Follow-up**: `test_types_contract.py` で tuple 変更不可、count property、`workspace_only` と `degraded` の違いを検証する。

### Decision: `workspace.yaml` は PyYAML safe loader で読む
- **Context**: current session metadata は YAML で保存され、Python 標準 library だけでは安全・互換的に parse できない。
- **Alternatives Considered**:
  1. 独自の簡易 YAML parser。依存は増えないが、format 差分に弱い。
  2. `PyYAML.safe_load`。依存は増えるが、Rails の `Psych.safe_load` と安全性・互換性の方向が近い。
  3. YAML を読まず event log だけで補完する。Requirement 2.2 を満たせない。
- **Selected Approach**: `PyYAML>=6.0.3,<7` を runtime dependency に追加し、`yaml.safe_load` のみを使う。
- **Rationale**: workspace metadata の正確な読取と parse failure 分類を実装可能にするため。
- **Trade-offs**: 新規 runtime dependency が増えるため、`pyproject.toml` と lock / container install の検証が必要になる。
- **Follow-up**: dependency install 後に `backend/bin/quality` で import、mypy、pytest を確認する。

### Decision: Search projection は基礎テキスト生成までに限定する
- **Context**: 要件は検索用テキストの元データを要求するが、semantic search や index 更新は対象外である。
- **Alternatives Considered**:
  1. BigQuery `search_text` row builder まで reader に含める。
  2. conversation/activity projection だけにし、検索元データを後続に任せる。
  3. reader 内に `SearchTextProjector` を置き、会話本文、preview、issue message の候補を返す。
- **Selected Approach**: `SearchTextProjector` が normalized session と conversation projection から `SearchTextSource` を返す。
- **Rationale**: 後続 repository が read model 更新に再利用でき、DB query や ranking は混入しない。
- **Trade-offs**: 最終 `search_text` の versioning は後続 persistence spec で固定する。
- **Follow-up**: issue 由来テキストの含め方を fixture で代表確認する。

## Risks & Mitigations
- current `workspace.yaml` が複雑な YAML tag や custom object を含むリスク。`yaml.safe_load` に限定し、mapping として扱えない payload は parse failure issue として返す。
- Rails と Python の timestamp / path / permission 判定が完全一致しないリスク。source state、issue code、event sequence の contract を優先し、OS 依存の permission test は分離する。
- Copilot CLI raw format が変わるリスク。unknown event と partial mapping を first-class contract にし、raw payload を保持する。
- 後続 API / repository の都合が reader に逆流するリスク。design の Out of Boundary と Revalidation Triggers で HTTP payload、BigQuery row、frontend 表示を明示的に除外する。

## References
- `.kiro/steering/product.md` — raw files 正本、current / legacy 共存、degraded data の原則。
- `.kiro/steering/tech.md` — Python / Django 移行、Docker Compose、quality command、read model 方針。
- `.kiro/steering/structure.md` — backend domain package と tests 配置の方針。
- `.kiro/specs/django-backend-foundation/design.md` — Python backend runtime と品質入口。
- `.kiro/specs/bigquery-read-model-schema/design.md` — downstream read model contract。
- `backend/lib/copilot_history/` — Rails 版 reader / normalizer / projector の互換参照実装。
- [PyYAML on PyPI](https://pypi.org/project/PyYAML/) — `workspace.yaml` 解析依存と Python 3.14 wheel availability の確認。

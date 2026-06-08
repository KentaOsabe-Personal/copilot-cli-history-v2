# 要件ドキュメント

## 導入

この spec は、Rails / MySQL で保持している `copilot_sessions` / `history_sync_runs` read model を、Django / BigQuery 移行で利用できる保存先契約として定義する。対象利用者は、後続の BigQuery repository、Django history API、parity validation を実装する開発者である。

BigQuery は Copilot CLI raw files の正本ではなく、同期で再生成できる read model として扱う。この spec は dataset / table schema、partition / clustering 方針、schema 初期化、環境変数と credentials 手順、実接続なしで検証できる fake repository 前提を固定し、implementation phase で opt-in の初期化手順を実行したときに実 BigQuery dataset / table を作成できる状態にする。sessions query / detail query / staging + MERGE の本実装は後続 spec に残す。

## 境界コンテキスト

- **In scope**: BigQuery dataset / table schema、`copilot_sessions` / `history_sync_runs` の保存項目契約、partition / clustering 方針、table 作成用 SQL の提示、schema 初期化手順、環境変数と credentials 手順、schema validation test、fake repository が満たす契約。
- **Out of scope**: Django ORM migration による BigQuery 管理、sessions list / detail query の実装、staging table + MERGE の本実装、Django API endpoint、Rails / MySQL 削除、Django admin / auth / session 用 DB 設計、高度な本番 GCP 運用設計。
- **Adjacent expectations**: `django-backend-foundation` は Python / Django の実行基盤と品質入口を提供する。`django-presenters-contract` は `summary_payload` / `detail_payload` の payload 互換を提供する。`bigquery-session-repository` はこの spec の schema 契約を参照して query / detail / upsert を実装する。

## 要件

### Requirement 1: BigQuery read model の schema 契約

**Objective:** As a 移行開発者, I want `copilot_sessions` と `history_sync_runs` の BigQuery schema contract を確認できる, so that 後続 repository と API が同じ read model 構造に依存できる。

#### 受け入れ基準

1. The BigQuery read model schema shall `copilot_sessions` table と `history_sync_runs` table の存在、主な列、必須性、型、既定値相当の扱いを文書または schema 定義で確認できる状態にする。
2. The BigQuery read model schema shall `copilot_sessions` に session identity、source format / state、source timestamps、workspace metadata、counts、degraded flag、conversation preview、source paths、source fingerprint、summary payload、detail payload、search text、search text version、indexed timestamp を保持できる契約を定義する。
3. The BigQuery read model schema shall `history_sync_runs` に sync lifecycle status、started / finished timestamps、processed / inserted / updated / saved / skipped / failed / degraded counts、failure / degradation summary、running lock identity を保持できる契約を定義する。
4. The BigQuery read model schema shall `summary_payload` と `detail_payload` を後続 presenter contract の JSON shape を失わず保存できる payload 領域として扱う。
5. The BigQuery read model schema shall raw Copilot history files を一次ソースから外さず、保存済み read model が再生成可能な補助層であることを明示する。

### Requirement 2: Partition / clustering と lookup 前提

**Objective:** As a repository 実装者, I want 日付範囲検索と session lookup を前提にした BigQuery table layout を確認できる, so that 後続 query が scan cost と既存 API contract を意識して実装できる。

#### 受け入れ基準

1. The BigQuery read model schema shall `copilot_sessions` の日付範囲取得で参照する source timestamp を partition filter の前提として明示する。
2. The BigQuery read model schema shall `copilot_sessions` の session id lookup、repository / branch 絞り込み、source format / state 確認に必要な clustering 候補を明示する。
3. The BigQuery read model schema shall `history_sync_runs` の直近 sync run 取得と status 確認に必要な partition または clustering 候補を明示する。
4. When 後続 repository が list query / detail query を設計するとき, the BigQuery read model schema shall 日付 range、session id、search text、sync status の利用前提を確認できる情報を提供する。
5. If 高度な BigQuery cost optimization が必要になった場合, the BigQuery read model schema shall この spec の初期 scope 外として扱える境界を明示する。

### Requirement 3: Dataset / table の初期化

**Objective:** As a backend 開発者, I want BigQuery dataset と table を再現可能に初期化できる, so that ローカル・検証・共有環境で同じ schema 契約を用意できる。

#### 受け入れ基準

1. When 開発者が schema 初期化手順を実行するとき, the BigQuery read model schema shall 必要な dataset と table を作成または既存 schema と照合できる。
2. When 初期化対象が既に存在するとき, the BigQuery read model schema shall schema の一致・不足・互換性のない差分を開発者が識別できる結果を返す。
3. If 必須環境変数または credentials が不足している場合, the BigQuery read model schema shall 外部接続前に不足項目を識別できる失敗として扱う。
4. The BigQuery read model schema shall schema 管理を Django ORM migration ではなく、BigQuery 用の明示的な初期化手順として扱う。
5. When implementation phase で BigQuery 初期化作業を実施するとき, the BigQuery read model schema shall 実行前に dataset / table 作成用 SQL を開発者へ提示する。
6. The BigQuery read model schema shall 初期化手順が後続 repository の query / upsert 実装を要求しないことを明示する。

### Requirement 4: 環境変数・credentials・local / test mode

**Objective:** As a 開発者, I want BigQuery 接続設定とローカル / test の使い分けを理解できる, so that 実接続が不要な作業と opt-in integration を混同せずに進められる。

#### 受け入れ基準

1. The BigQuery read model schema shall project id、dataset id、table prefix または table names、location、credentials に関する必要設定を文書化する。
2. The BigQuery read model schema shall 通常の unit test と settings import が BigQuery 実接続を必須にしないことを明示する。
3. Where 実 BigQuery dataset を使う integration validation が含まれる, the BigQuery read model schema shall opt-in 条件と必要な環境変数を明示する。
4. If credentials が開発者環境に存在しない場合, the BigQuery read model schema shall fake repository または schema-only validation で作業を継続できる前提を示す。
5. The BigQuery read model schema shall secrets や credentials 内容を repository に保存しない運用前提を明示する。

### Requirement 5: Fake repository と schema validation の契約

**Objective:** As a 後続 spec 実装者, I want fake repository と schema validation の期待値を確認できる, so that BigQuery 実接続なしで repository / API unit test を作成できる。

#### 受け入れ基準

1. The BigQuery read model schema shall fake repository が `copilot_sessions` と `history_sync_runs` の必須フィールド、状態値、count fields、payload fields を検証できる前提を定義する。
2. The BigQuery read model schema shall schema validation test が table schema、partition / clustering 設定、必須列、JSON payload 領域、timestamp / count fields を検証対象に含めることを明示する。
3. When 後続 unit test が fake repository を使うとき, the BigQuery read model schema shall BigQuery client や実 dataset への接続なしで主要保存契約を検証できる前提を提供する。
4. If fake repository と BigQuery schema contract の差分が見つかった場合, the BigQuery read model schema shall 差分を schema 契約違反として扱える判断材料を提供する。
5. The BigQuery read model schema shall API response shape の変更や presenter payload の再定義をこの spec の検証対象に含めない。

### Requirement 6: 移行境界と後続 spec への引き継ぎ

**Objective:** As a spec reviewer, I want この spec の完了条件と隣接 spec への引き渡しを確認できる, so that BigQuery repository と Django API の実装前に datastore contract の合意を得られる。

#### 受け入れ基準

1. The BigQuery read model schema shall `bigquery-session-repository` が参照できる dataset / table / environment / fake repository の契約を残す。
2. The BigQuery read model schema shall Rails / MySQL read model の削除を完了条件に含めない。
3. The BigQuery read model schema shall Django API endpoint、request validation、HTTP response、frontend 接続変更を完了条件に含めない。
4. When reviewer が requirements / design / tasks を確認するとき, the BigQuery read model schema shall inclusion、exclusion、adjacent expectations を追跡できる境界情報を保持する。
5. The BigQuery read model schema shall 現行 API contract と raw file 正本のプロダクト原則を変更しない。

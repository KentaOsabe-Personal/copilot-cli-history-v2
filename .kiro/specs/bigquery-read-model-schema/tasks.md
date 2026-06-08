# Implementation Plan

- [x] 1. Django BigQuery read model の実装基盤を追加する
- [x] 1.1 backend Python package と依存関係を BigQuery read model 用に登録する
  - Django が `history_read_model` app と management command を discover できるようにする
  - `google-cloud-bigquery` は runtime dependency として解決できるが、settings import 時には client が生成されない状態にする
  - package discovery と app registration 後に既存 Django foundation tests が引き続き import できることを確認できる
  - _Requirements: 3.4, 4.2, 6.1_

- [x] 1.2 BigQuery 接続設定と opt-in 実行条件を検証する
  - project id、dataset id、location、table prefix、credentials / ADC 利用可否、integration flag の env 契約を読み取れるようにする
  - execute / compare mode では必須 env と credentials 不足を BigQuery 接続前に列挙して失敗させる
  - dry-run / unit mode では credentials がなくても設定 import と schema-only validation を継続できることを確認できる
  - secrets や credentials 内容を repository に保存せず、エラーや出力にも credential content を含めない
  - _Requirements: 3.3, 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 2. BigQuery schema contract を実装する
- [ ] 2.1 `copilot_sessions` の table schema 契約を固定する
  - session identity、source format / state、source timestamps、workspace metadata、counts、degraded flag、conversation preview、source paths、source fingerprint、summary payload、detail payload、search text、search text version、indexed timestamp を保持する列契約を定義する
  - required / nullable、BigQuery type、default equivalent、enum、non-negative count invariant、JSON object payload 領域を確認できるようにする
  - `summary_payload` と `detail_payload` は presenter JSON shape を失わず保存する JSON 領域として扱い、raw files は一次ソースで read model は再生成可能な補助層である前提を schema 契約から追跡できる
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 5.2, 6.5_

- [ ] 2.2 `history_sync_runs` の table schema 契約を固定する
  - sync lifecycle status、started / finished timestamps、processed / inserted / updated / saved / skipped / failed / degraded counts、failure / degradation summary、running lock identity を保持する列契約を定義する
  - required / nullable、BigQuery type、default equivalent、terminal / running lifecycle invariant、saved count invariant を確認できるようにする
  - 後続 repository が sync status と直近 run の保存契約を BigQuery 実接続なしで参照できる状態にする
  - _Requirements: 1.1, 1.3, 5.2, 6.1_

- [ ] 2.3 partition / clustering と table naming の layout 契約を固定する
  - `copilot_sessions` は日付 range 用の `source_partition_date` partition と session / repository / branch / source format clustering を契約化する
  - `history_sync_runs` は started_at 由来 partition と status / started_at / running lock clustering を契約化する
  - prefix 付き table names を in-scope の設定契約として扱い、高度な cost optimization だけを初期 scope 外として確認できる
  - 後続 list / detail query 設計が date range、session id、search text、sync status の利用前提を参照できる状態にする
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 6.1_

- [ ] 3. SchemaDefinition から DDL と metadata comparison を生成する
- [ ] 3.1 dataset / table 作成 SQL と metadata 取得 SQL を dry-run 表示できる形で生成する
  - dataset 作成 SQL と 2 table の `CREATE TABLE IF NOT EXISTS` SQL を schema 契約から決定的に生成する
  - `--compare` 用に `INFORMATION_SCHEMA.COLUMNS` / `TABLE_OPTIONS` を取得する comparison SQL を生成する
  - SQL には partition、clustering、`require_partition_filter`、JSON columns、safe identifier handling が反映される
  - 実行前に target dataset / tables、作成 SQL、比較用 metadata query を開発者が確認できる出力を生成できる
  - _Requirements: 3.1, 3.4, 3.5, 5.2_
  - _Boundary: DDLBuilder_

- [ ] 3.2 (P) 既存 BigQuery metadata と schema 契約の差分分類を実装する
  - column name、type、nullability、partition / clustering related options を expected schema と比較する
  - missing / incompatible / extra informational を決定的に分類し、missing または incompatible がある場合は compatible false として扱う
  - 既存 table に余分な列がある場合は自動削除せず informational として報告できる
  - _Depends: 2.1, 2.2, 2.3_
  - _Requirements: 3.1, 3.2, 5.2, 5.4_
  - _Boundary: MetadataComparator_

- [ ] 4. BigQuery 実接続なしの fake repository 契約を実装する
  - session row と sync run row の required fields、enum、count fields、payload object、search text version、sync lifecycle を保存前に検証する
  - valid rows は in-memory に保存され、invalid rows は契約違反として失敗する
  - fake は SchemaDefinition を共有参照し、schema required fields や enum と fake validation がずれた場合に契約違反として検出できる
  - fake は BigQuery client や実 dataset に接続せず、後続 repository / API unit test が保存契約を検証できる状態にする
  - API response shape や presenter payload の再定義は fake の責務に含めない
  - _Requirements: 4.4, 5.1, 5.3, 5.4, 5.5, 6.1, 6.5_
  - _Boundary: FakeRepository_

- [ ] 5. 初期化 management command を統合する
- [ ] 5.1 dry-run first の初期化 command を追加する
  - 既定実行では BigQuery client を生成せず、target dataset / tables と作成 SQL を stdout に提示する
  - `--execute` のときだけ BigQuery client を作成し、dataset / tables を create-if-missing で用意する
  - repository query / detail / staging + MERGE upsert を呼び出さないことが command の境界として確認できる
  - _Depends: 1.2, 3.1_
  - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6, 4.3_

- [ ] 5.2 compare mode で既存 schema 照合結果を表示する
  - `--compare` のときだけ information schema metadata を取得し、metadata comparator の結果を stdout / stderr に表示する
  - schema 一致、不足、非互換差分、追加情報を開発者が識別できる result summary と diff details を返す
  - 非互換差分は失敗として扱い、destructive change や自動 ALTER は実行しない
  - _Depends: 3.1, 3.2, 5.1_
  - _Requirements: 3.1, 3.2, 3.3, 4.3, 5.2_

- [ ] 6. Schema-only と command behavior のテストを追加する
- [ ] 6.1 schema contract と DDL generation の単体テストを追加する
  - table schema、必須列、型、nullable、enum、timestamp / count fields、JSON payload 領域、partition / clustering 設定を検証する
  - DDL が dataset / table、partition、clustering、`require_partition_filter`、JSON columns、metadata comparison query を含むことを検証する
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す
  - _Depends: 2.1, 2.2, 2.3, 3.1_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 5.2_

- [ ] 6.2 settings と fake repository の単体テストを追加する
  - env 欠落が外部接続前に識別され、unit / dry-run mode では credentials を要求しないことを検証する
  - fake repository が required fields、status / source enum、count invariant、payload object、search text version を検証することを確認する
  - fake repository が SchemaDefinition と共有する required fields / enum から drift を契約違反として検出できることを確認する
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す
  - _Depends: 1.2, 4_
  - _Requirements: 3.3, 4.2, 4.4, 5.1, 5.3, 5.4_

- [ ] 6.3 metadata comparator の単体テストを追加する
  - missing column、type mismatch、mode mismatch、partition / clustering mismatch を incompatible として検証する
  - extra column は informational として扱われ、自動削除や失敗扱いにしないことを検証する
  - diff categories と compatible 判定が command 表示に使える決定的な結果になることを確認する
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す
  - _Depends: 3.2_
  - _Requirements: 3.2, 5.2, 5.4_

- [ ] 6.4 command integration tests と opt-in integration guard を追加する
  - Django command discovery、default dry-run output、client 非生成、fake client による execute / compare path を検証する
  - 実 BigQuery dataset を使う validation は integration flag と required env / credentials が揃った場合だけ動くようにする
  - 通常テストで BigQuery 実接続が発生しないことを確認できる
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す
  - _Depends: 5.1, 5.2_
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 4.2, 4.3, 4.4_

- [ ] 7. BigQuery read model contract の完了境界を検証する
  - Django foundation の既存品質入口で package registration、settings import、schema-only tests が通ることを確認する
  - BigQuery 実接続なしでも後続 `bigquery-session-repository` が参照できる dataset / table / env / fake repository 契約が揃っていることを確認する
  - Rails / MySQL read model 削除、Django API endpoint、request validation、HTTP response、frontend 接続変更が変更範囲に含まれていないことを確認する
  - _Depends: 1.1, 6.1, 6.2, 6.3, 6.4_
  - _Requirements: 1.5, 3.6, 4.2, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_

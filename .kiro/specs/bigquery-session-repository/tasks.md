# Implementation Plan

- [x] 1. Repository 契約と実行前提を固定する
- [x] 1.1 read model repository の共通操作、結果、error 分類を定義する
  - 一覧取得、詳細取得、session 保存、sync run 保存、running sync 検出を同じ repository 契約として呼び出せるようにする。
  - summary payload と detail payload は presenter-compatible な保存済み JSON object として透過的に扱い、repository 内で別 shape を作らない。
  - 日付 range 欠落、無効な limit、空の session ID、validation 失敗、BigQuery 実行失敗を呼び出し側が識別できる結果にする。
  - 完了時には、API と同期処理が BigQuery client や raw file reader を知らずに同じ repository operation を参照できる。
  - _Requirements: 1.1, 1.4, 1.5, 2.9, 3.4, 5.2, 5.3, 5.5_

- [x] 1.2 BigQuery 実行オプションと runtime prerequisite を整理する
  - dry run、maximum bytes billed、location、integration test opt-in 条件を repository 実行に渡せるようにする。
  - settings import や通常 unit test で BigQuery client や credentials を必須にしない。
  - maximum bytes billed の既定値を使う場合でも、明示上限と dry run の結果が呼び出し側に見えるようにする。
  - 完了時には、credentials がない開発環境でも fake と SQL validation の unit test を実行でき、実接続検証だけが opt-in になる。
  - _Requirements: 5.3, 5.4, 5.5, 6.4, 6.5_

- [x] 2. 保存 row 境界と同期分類を実装する
- [x] 2.1 normalized session から read model 保存入力を組み立てる境界を作る
  - raw files を一次ソース、read model を再生成可能な保存先として扱う入力変換にする。
  - schema 契約に適合する session row と sync run row だけを保存候補にし、payload は presenter contract の shape を保持する。
  - workspace only の session は表示用 read model へ保存しない候補として分類できるようにする。
  - degraded 状態と issue 情報は後続表示で識別できる payload として失わせない。
  - 完了時には、保存候補、workspace only 候補、契約違反候補が repository write の前段で区別できる。
  - _Requirements: 1.2, 1.3, 1.4, 4.5, 4.6, 6.2_

- [x] 2.2 同期保存の insert / update / skip / invalid 分類と件数契約を実装する
  - 新規 session ID は insert、既存 session ID で fingerprint または検索 projection が異なるものは update として分類する。
  - fingerprint と検索 projection が保存済み metadata と一致する session は skip として分類する。
  - workspace only と invalid row は BigQuery の保存対象から外し、skipped / failed の件数に反映する。
  - processed、inserted、updated、saved、skipped、failed、degraded の件数 invariant を BigQuery job statistics に依存せず算出する。
  - 完了時には、同じ入力と既存 metadata から fake adapter と BigQuery adapter が同じ write plan と件数を得られる。
  - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.7, 6.3_

- [x] 3. 一覧・詳細の read path を実装する
- [x] 3.1 fake repository で list / detail lookup の代表挙動を提供する
  - 表示日時は更新日時優先、欠落時は作成日時 fallback とし、両方欠落した session は日付 range 候補から外す。
  - 日付 range と検索語は AND 条件で適用し、検索語は保存済み検索対象または作業ディレクトリ情報に一致させる。
  - 表示日時降順、同一表示日時では session ID 昇順で安定順序にし、正の limit は条件と並び順の後に適用する。
  - detail lookup は保存済み detail payload をそのまま返し、存在しない session ID は not found として識別できる結果にする。
  - 完了時には、BigQuery 実接続なしで list、empty result、detail、not found、current / legacy lookup の契約を検証できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.5_

- [x] 3.2 (P) BigQuery list / detail 用の parameterized query を生成する
  - list query は partition 前提の日付条件と表示日時 expression の両方で候補を絞る。
  - 検索語、日付 range、limit、session ID は named parameter として扱い、user input を SQL へ直接埋め込まない。
  - 検索対象は保存済み検索対象と作業ディレクトリ情報に限定し、repository metadata を暗黙に検索対象へ増やさない。
  - detail lookup は raw files を読まず、保存済み detail payload を session ID で取得する query にする。
  - 完了時には、生成 SQL に partition filter、安定 ordering、limit、detail lookup 条件、named parameters が確認できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.4, 3.5, 5.1, 5.4_
  - _Boundary: SQLBuilder_
  - _Depends: 1.1, 1.2_

- [x] 3.3 (P) BigQuery failure を repository error へ分類する
  - credentials、permission、schema mismatch、cost limit、query failure を呼び出し側が識別できる kind に分類する。
  - maximum bytes billed 超過や job failure を success result と混同しない。
  - validation failure と BigQuery job-level failure を row-level failed count から分離する。
  - 完了時には、BigQuery client exception と job result failure が repository error kind として安定して返る。
  - _Requirements: 5.4, 5.5_
  - _Boundary: ErrorMapper_
  - _Depends: 1.1_

- [ ] 4. 同期保存と BigQuery adapter を統合する
- [x] 4.1 fake repository で save sessions と sync run lifecycle を提供する
  - 保存対象 session 群を write plan に従って in-memory read model の最新状態へ反映する。
  - insert、update、skip、workspace only、invalid、degraded の代表ケースを同じ result contract で返す。
  - running、succeeded、failed、completed_with_issues の sync run を保存し、未完了 sync run を running lock として検索できるようにする。
  - 完了時には、fake repository だけで session 保存、sync run 保存、running sync 検出、row contract 違反を検証できる。
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 6.1, 6.2, 6.5_

- [x] 4.2 (P) BigQuery write path 用の metadata lookup、staging、MERGE、sync run query を生成する
  - 保存候補 session ID だけを対象に既存 metadata を取得し、分類に必要な field だけを返す query にする。
  - insert / update 対象だけを staging と MERGE の対象にし、skip、workspace only、invalid row は target table に投入しない。
  - MERGE は session ID identity で重複 row を作らず、partitioned table の pruning を妨げない構造にする。
  - sync run の start / finish 保存と running sync 検出に必要な query を生成する。
  - 完了時には、write dry run でも実行予定の metadata lookup、staging、MERGE、sync run 操作が検証可能になる。
  - _Requirements: 4.1, 4.3, 4.8, 4.9, 5.3, 5.4_
  - _Boundary: SQLBuilder_
  - _Depends: 2.2_

- [x] 4.3 BigQuery adapter で read / write / sync run operation を実行する
  - repository criteria と execution options から BigQuery job config を作り、named parameters、dry run、maximum bytes billed、location を適用する。
  - list と detail は保存済み summary / detail payload を返し、日付 range 欠落や invalid input では BigQuery job を作らない。
  - save sessions は既存 metadata 取得、write plan 分類、staging、MERGE、sync run 保存を順に実行し、dry run では実 data mutation を行わない。
  - BigQuery exception と job failure は分類済み repository error として返し、credentials や schema 不整合を呼び出し側が識別できるようにする。
  - 完了時には、BigQuery client を注入した adapter が repository port の全 operation を同じ result contract で実行できる。
  - _Requirements: 1.1, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.3, 5.4, 5.5_
  - _Depends: 2.1, 2.2, 3.2, 3.3, 4.2_

- [x] 5. Repository 契約の unit / contract tests を整備する
- [x] 5.1 write planner の分類と count invariant を検証する
  - 新規、更新、skip、workspace only、invalid、degraded の分類を BigQuery 非依存で検証する。
  - saved count、processed count、skipped count、failed count、degraded count の invariant を確認する。
  - job-level error が row-level failed count に混入しないことを確認する。
  - 完了時には、各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントがあり、planner の保存分類契約を説明している。
  - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.7, 6.6_

- [x] 5.2 fake repository の read / write / sync lifecycle 契約を検証する
  - display time fallback、日付 range、検索語、AND 条件、stable ordering、limit、empty result を検証する。
  - detail payload passthrough、current / legacy lookup、not found、raw files 非依存を検証する。
  - save sessions、degraded、sync run lifecycle、running lock、row contract 違反を検証する。
  - 完了時には、BigQuery credentials がない環境でも fake repository の主要契約 test が成功する。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 6.1, 6.2, 6.5, 6.6_

- [x] 5.3 BigQuery SQL と job option の安全性を検証する
  - list query の partition predicate、display time expression、search literal escaping、named parameters、limit、ordering を検証する。
  - detail lookup、metadata lookup、MERGE、sync run query が対象 field と identity 条件を満たすことを検証する。
  - dry run と maximum bytes billed が query execution に渡る構造を検証する。
  - 完了時には、SQL test が user input の直埋めや partition filter 欠落を検出できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.3, 4.8, 4.9, 5.1, 5.3, 5.4, 6.6_

- [x] 5.4 BigQuery adapter の error mapping と dry run 挙動を検証する
  - credentials、permission、schema mismatch、cost limit、query failure が repository error kind へ分類されることを検証する。
  - missing date range や invalid input では BigQuery job が作られないことを検証する。
  - dry run の list、detail、write が実 data mutation を行わず、検証結果または実行予定内容を返すことを検証する。
  - 完了時には、BigQuery client の例外や job failure が success として扱われない。
  - _Requirements: 5.2, 5.3, 5.4, 5.5, 6.6_

- [x] 5.5 fake と BigQuery adapter の shared contract tests を追加する
  - list 条件、detail lookup、not found、保存件数、degraded、sync run 状態の代表挙動を同じ assertion で検証する。
  - BigQuery adapter 側は実接続なしで検証できる client double または dry run 経路を使い、通常 unit test を credentials に依存させない。
  - fake と BigQuery adapter の count result が同じ write plan に基づくことを確認する。
  - 完了時には、adapter 間の contract drift が shared tests で検出できる。
  - _Requirements: 6.3, 6.5, 6.6_

- [x] 5.6 opt-in BigQuery integration test の gate を追加する
  - integration flag と必要 env が揃う場合だけ実 BigQuery dataset で代表 list、detail、write を実行する。
  - credentials や env がない通常環境では skip し、fake と SQL / contract validation は継続する。
  - 実接続 test は schema 初期化をこの feature の責務にせず、既存 read model schema を前提にする。
  - 完了時には、opt-in 条件が満たされた環境でのみ BigQuery 実接続検証が走る。
  - _Requirements: 6.4, 6.5, 6.6_

- [ ] 6. Package 統合と品質ゲートを通す
- [ ] 6.1 repository 実装を backend package から利用できる状態に統合する
  - port、fake、BigQuery adapter、SQL、error mapping、write planner が package 内の一貫した依存方向で import できるようにする。
  - BigQuery client 生成は adapter 境界に閉じ、Django settings import や fake 利用時に実接続を要求しない。
  - endpoint、HTTP status 判定、raw file parsing、schema 初期化、Search Index、semantic search はこの統合に含めない。
  - 完了時には、後続の Django API / sync service spec が repository port を import して利用できる。
  - _Requirements: 1.1, 1.5, 5.5, 5.6, 6.1, 6.5_

- [ ] 6.2 lint、type check、repository tests を実行して回帰を解消する
  - repository 関連の unit、contract、SQL、error mapping tests を実行し、失敗があれば原因を実装または test contract 側で解消する。
  - mypy strict と ruff の対象範囲で、repository 追加分が既存品質基準を満たすようにする。
  - 追加・更新した pytest test case がすべて `概要・目的`、`テストケース`、`期待値` コメントを持つことを確認する。
  - 完了時には、BigQuery credentials がない通常環境でも repository の主要検証が成功し、残る実接続検証は opt-in skip として説明できる。
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

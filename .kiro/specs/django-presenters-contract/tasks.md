# Implementation Plan

- [x] 1. Presenter 契約の基盤を用意する
- [x] 1.1 API Presenter 専用の入力型と package 境界を作る
  - Presenter が repository object、Django request、HTTP status を受け取らずに response body を生成できる入力型を用意する。
  - session detail projection、tool call、conversation、activity、timeline、sync run、sync counts、validation error、root failure の値を型付きで表せるようにする。
  - sync result kind ごとの必須値と counts の非負条件を fail fast で検出できるようにする。
  - 完了時には downstream API 未実装でも Presenter tests から必要な入力を構築でき、mypy strict で unsafe cast なしに参照できる。
  - _Requirements: 1.4, 1.5, 3.2, 3.3, 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.3, 6.5, 7.4, 7.5_

- [x] 1.2 fixture 比較のテスト基盤を作る
  - `api-contract-fixtures` の manifest と response body を読み、代表 scenario ごとに expected body を取得できるようにする。
  - generated body と fixture body の最初の差分 field path と scenario id を表示する helper を用意する。
  - 新規 pytest の各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く規約を適用する。
  - 完了時には fixture deep equality の失敗が、どの scenario のどの field path で発生したかを pytest 出力から判断できる。
  - _Requirements: 1.1, 7.1, 7.2, 7.3_

- [x] 2. Session response projection を実装する
- [x] 2.1 issue envelope 変換を実装する
  - reader issue の code、severity、message、source_path を改名せずに response issue envelope へ変換する。
  - sequence がない issue は session scope、sequence がある issue は event scope として event_sequence を保持する。
  - 完了時には session issue と event issue が同じ schema で返り、scope と event_sequence の差分だけで配置先を判断できる。
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 2.2 session 一覧用 summary projection を実装する
  - current / legacy の session を同じ summary schema に変換し、source_format の違い以外で field set を分岐させない。
  - id、source_format、created_at、updated_at、work_context、selected_model、source_state、event_count、message_snapshot_count、conversation_summary、degraded、issues を生成する。
  - conversation がある場合とない場合の has_conversation、message_count、preview、activity_count、null 表現を fixture と同じ意味で返す。
  - 完了時には summary 単体の出力が frontend session API 型で期待される field 名、nullable、配列構造を満たす。
  - _Requirements: 1.4, 2.1, 2.2, 2.3, 2.4, 4.3_

- [x] 2.3 session 詳細用 projection を実装する
  - session header、message snapshots、conversation、activity、timeline を response 用 nested 部品として生成する。
  - timeline event は message、detail、unknown の kind ごとに sequence、mapping_status、raw_type、occurred_at、role、content、tool_calls、detail、degraded、issues を保持する。
  - activity entry は category、title、summary、raw_type、mapping_status、occurred_at、source_path、raw_available、degraded、issues を mapping 表に従って導出する。
  - event issue は sequence ごとに timeline / conversation / activity の該当 entry へ分配し、他 entry の degraded を変更しない。
  - 完了時には partial mapping や unknown event でも読み取れた field が残り、該当 issue が既存 issue schema で entry に紐づく。
  - _Requirements: 1.4, 3.1, 3.2, 3.3, 4.2, 4.4, 4.5_

- [x] 2.4 raw payload opt-in の切替を projection に組み込む
  - include raw が false の場合は detail response 全体で raw_included を false にし、timeline、activity、message snapshot の raw_payload を null にする。
  - include raw が true の場合は raw payload が存在する entry に fixture と同じ raw value を返し、存在しない entry は null のままにする。
  - raw_available は raw payload の有無を示し、raw_included の値で変化しないようにする。
  - 完了時には同じ normalized session から raw なし詳細と raw 付き詳細の両方を生成でき、差分が raw_included と raw_payload に限定される。
  - _Requirements: 3.4, 3.5, 7.4_

- [x] 3. Session success Presenter を実装する
- [x] 3.1 session list response body を生成する
  - 入力順を維持した session summary 配列を top-level data に配置する。
  - meta.count に返却 session 数、meta.partial_results に degraded session の有無を反映する。
  - filtering、sorting、limit、repository query は行わず、body factory の責務に閉じる。
  - 完了時には一覧 success fixture と同じ top-level data / meta envelope を返せる。
  - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 2.5, 4.3, 7.5_

- [x] 3.2 session detail response body を生成する
  - session header、issues、message_snapshots、conversation、activity、timeline を top-level data に配置する。
  - session level issue は data.issues に置き、event level issue は projection 済み entry 側に残す。
  - include_raw の真偽だけで raw_included と raw_payload 表現を切り替える。
  - 完了時には詳細 success、raw なし詳細、raw 付き詳細の fixture と同じ success envelope を返せる。
  - _Requirements: 1.1, 1.2, 1.5, 3.1, 3.4, 3.5, 4.1, 4.3, 7.5_

- [x] 4. Sync と common error Presenter を実装する
- [x] 4.1 (P) history sync response body を生成する
  - succeeded と completed_with_issues は error envelope ではなく data.sync_run と data.counts を含む success body にする。
  - running conflict は history_sync_running code と running run の id / started_at を details に含む error body にする。
  - root failure と persistence failure は fixture と同じ error body、sync run meta、counts を返す。
  - 完了時には sync result kind ごとに success envelope と error envelope が混在せず、HTTP status を返さない body factory として使える。
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.4, 6.5, 7.5_
  - _Boundary: HistorySyncPresenter_
  - _Depends: 1.1_

- [x] 4.2 (P) common error response body を生成する
  - session not found は session_not_found code、固定 message、session_id details を返す。
  - validation error は upstream validation result の code、message、details を改名せずに返す。
  - root failure は root failure code、message、path details を保持する。
  - 完了時には top-level key が error のみになり、success envelope の data / meta と混在しない。
  - _Requirements: 1.1, 1.3, 1.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.5_
  - _Boundary: ErrorPresenter_
  - _Depends: 1.1_

- [x] 5. Presenter contract tests を実装する
- [x] 5.1 session list の代表 fixture と Presenter 出力を比較する
  - list_success、list_empty、list_degraded の response body と session list Presenter 出力を deep equality で比較する。
  - current / legacy 混在、empty conversation、degraded session、meta.count、meta.partial_results を fixture と照合する。
  - 各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く。
  - 完了時には一覧 response shape drift が fixture 差分として検出され、scenario id と field path が確認できる。
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 4.3, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5.2 session detail の代表 fixture と Presenter 出力を比較する
  - detail_success、detail_without_raw、detail_with_raw の response body と session detail Presenter 出力を deep equality で比較する。
  - timeline、conversation、activity、message snapshots、raw_included、raw_payload、issue 分配を fixture と照合する。
  - 各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く。
  - 完了時には raw なし / raw 付きの詳細 response shape drift が fixture 差分として検出される。
  - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.4, 4.5, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5.3 history sync の代表 fixture と Presenter 出力を比較する
  - succeeded、completed_with_issues、running conflict、root failure、persistence failure の response body と sync Presenter 出力を deep equality で比較する。
  - success body と error body の envelope、sync_run、counts、failure details、meta を fixture と照合する。
  - 各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く。
  - 完了時には sync response shape drift が fixture 差分として検出される。
  - _Requirements: 1.1, 1.2, 1.3, 5.1, 5.2, 5.3, 5.4, 5.5, 6.4, 6.5, 7.1, 7.2, 7.3_
  - _Depends: 1.2, 4.1_

- [x] 5.4 common error の代表 fixture と Presenter 出力を比較する
  - session not found と session list validation の response body を common error Presenter 出力と deep equality で比較する。
  - error.code、error.message、error.details の key と object 表現を fixture と照合する。
  - 各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く。
  - 完了時には common error envelope の drift が fixture 差分として検出される。
  - _Requirements: 1.1, 1.3, 6.1, 6.2, 6.4, 6.5, 7.1, 7.2, 7.3_
  - _Depends: 1.2, 4.2_

- [x] 6. 境界条件と品質ゲートを確認する
- [x] 6.1 Presenter 境界の単体 tests を追加する
  - issue scope、empty conversation、tool-only assistant、unknown / partial event、tool_calls.status、activity title / summary / source_path / raw_available を小さな input で検証する。
  - not found、validation、root failure の details key 保持を common error Presenter の単体 test で検証する。
  - 各 test case 直前に `概要・目的`、`テストケース`、`期待値` コメントを置く。
  - 完了時には fixture 代表例だけでは見えにくい raw opt-in、issue 分配、nullable、fallback 導出の契約が pytest で保護される。
  - _Requirements: 1.4, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.4, 4.5, 6.1, 6.2, 6.3, 6.5, 7.3, 7.4, 7.5_

- [x] 6.2 backend quality commands で Presenter 契約を検証する
  - pure Python pytest で Presenter contract tests と boundary tests が通ることを確認する。
  - ruff と mypy strict で API presentation types、projection、Presenter、tests の型と style を確認する。
  - Django request client、BigQuery、filesystem reader、repository query に依存しない検証になっていることを確認する。
  - 完了時には backend の既存品質入口で失敗なく検証でき、Presenter package が後続 Django API から body factory として利用できる状態になる。
  - _Requirements: 1.5, 7.1, 7.2, 7.4, 7.5_

# Implementation Plan

- [x] 1. 契約 fixture 作成の土台を整える
- [x] 1.1 fixture set の scenario 分類と最小構成を確定する
  - 対象 endpoint、代表 scenario、成功 payload と error envelope の分類を fixture set 内で迷わず追加できる状態にする。
  - request fixture と response fixture が status、query/body、success/error 種別を一貫して表せるようにする。
  - 完了時には、後続 task が endpoint 別 fixture を同じ規則で追加できる。
  - _Requirements: 1.1, 1.2_

- [x] 1.2 契約正本と対象外境界を fixture set の前提として固定する
  - 現行 Rails API、request spec、presenter、frontend 型を正本として扱う前提を明示する。
  - API shape 変更、新規 UI、移行先 backend、分析 schema、reader 移植、既存 stack 削除がこの spec の対象外であることを明示する。
  - fixture 更新時に更新理由、対象 endpoint、影響 frontend 型、status code と error code の変更有無を記録する流れを定義する。
  - 完了時には、fixture 差分を仕様変更候補と移植バグに分けてレビューできる。
  - _Requirements: 1.3, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. endpoint 別の代表 fixture を作成する
- [x] 2.1 (P) セッション一覧の成功、空結果、検索条件 fixture を作成する
  - list success が top-level `data` 配列と `meta` object を持ち、summary fields を frontend が参照できる形で示す。
  - empty / no match が HTTP 200、空配列、count 0、partial_results false として表れるようにする。
  - date range と search query の request と期待 response の対応を示す。
  - 完了時には、一覧 UI が通常結果と該当なし結果の response shape を fixture から確認できる。
  - _Depends: 1.1_
  - _Requirements: 2.1, 2.2, 2.3, 2.5, 6.1_
  - _Boundary: ScenarioFixtures - SessionIndex_

- [x] 2.2 セッション一覧の degraded と validation error fixture を作成する
  - degraded session が session-level issues と `meta.partial_results: true` を同時に示す。
  - invalid date range、invalid datetime、invalid limit、overlong search、control character の validation error を HTTP 400 として示す。
  - validation error details に field、reason、必要な value が含まれるようにする。
  - 完了時には、一覧 API の partial result と invalid query の契約を fixture から判定できる。
  - _Requirements: 2.4, 5.1, 5.3, 5.4, 5.5, 6.1, 6.4_

- [x] 2.3 (P) セッション詳細と raw opt-in fixture を作成する
  - 通常詳細が top-level `data` object、conversation、activity、timeline の代表 shape を示す。
  - raw 未要求時は raw payload fields が null または非表示相当として扱われ、通常詳細表示が raw payload を要求しないことを示す。
  - raw opt-in request では `raw_included: true` と代表 raw payload が返る箇所を示す。
  - 完了時には、通常詳細表示と raw payload 表示の境界を fixture から確認できる。
  - _Depends: 1.1_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.2_
  - _Boundary: ScenarioFixtures - SessionShow_

- [x] 2.4 (P) セッション詳細 not found fixture を作成する
  - missing session が HTTP 404 と `session_not_found` error envelope を示し、要求 session id を details に含める。
  - frontend が 404 `session_not_found` を dedicated not-found state として扱える status / code 対応を示す。
  - 完了時には、存在しない session の detail request が共通 error envelope と frontend normalization の両方に対応していることを fixture で確認できる。
  - _Depends: 1.1_
  - _Requirements: 5.1, 5.2, 5.5, 6.4_
  - _Boundary: ScenarioFixtures - SessionShowErrors_

- [x] 2.5 (P) 履歴同期の成功・失敗 fixture を作成する
  - sync success と completed_with_issues が HTTP 200、sync_run、counts、degraded_count、保存 issue 情報を示す。
  - sync conflict、root failure、persistence failure がそれぞれ HTTP 409、503、500 と expected error envelope / meta を示す。
  - 完了時には、同期 API の成功、劣化成功、競合、読み取り失敗、永続化失敗を fixture で比較できる。
  - _Depends: 1.1_
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 6.3, 6.4_
  - _Boundary: ScenarioFixtures - HistorySync_

- [x] 3. contract note と manifest で fixture set を統合する
- [x] 3.1 endpoint inventory と status / error code matrix を完成させる
  - 各対象 endpoint について代表 request、期待 HTTP status、成功 payload または error envelope の検証対象を一覧化する。
  - 404 `session_not_found` は dedicated not-found state、それ以外の backend error は backend error として扱える対応を示す。
  - 現行 API と frontend 型の命名、nullable、field presence 差分があれば期待値の根拠とともに記録する。
  - 完了時には、対象範囲、対象外、status / error code の判断を contract note だけで追える。
  - _Depends: 2.1, 2.2, 2.3, 2.4, 2.5_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.5_

- [x] 3.2 frontend 型対応と field coverage note を完成させる
  - list、detail、sync、error fixture と対応する frontend 型を表で確認できるようにする。
  - 代表 fixture に含まれない frontend field は、対象外、別 fixture で検証、契約欠落候補のいずれかに分類する。
  - raw opt-in、tool call、timeline、error normalization に関わる型対応を downstream spec が参照できる状態にする。
  - 完了時には、fixture 更新時に UI 依存 field の欠落を contract note から検出できる。
  - _Depends: 2.1, 2.2, 2.3, 2.4, 2.5_
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3.3 manifest で全 scenario と fixture path を機械可読にする
  - scenario ID、method、endpoint、status、request / response、関連 requirement ID、関連 frontend 型を列挙する。
  - manifest から参照される request / response fixture が存在し、scenario と status が一致する状態にする。
  - requirement coverage は numeric ID のみで記録する。
  - 完了時には、後続 Django presenter / API / parity validation が manifest から期待 fixture を発見できる。
  - _Depends: 2.1, 2.2, 2.3, 2.4, 2.5, 3.2_
  - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3, 6.4, 7.4_

- [x] 4. fixture validation を追加して契約 artifact を検証する
- [x] 4.1 backend の軽量 fixture validation test を追加する
  - manifest と全 request / response fixture が JSON として parse できることを検証する。
  - success response は endpoint 種別ごとの top-level shape、error response は common error envelope を検証する。
  - 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す。
  - 完了時には、fixture の構文破損と代表必須 field 欠落が RSpec failure として見える。
  - _Depends: 3.3_
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 5.1, 7.5_

- [x] 4.2 validation と coverage を実行して fixture set を仕上げる
  - fixture validation test を実行し、manifest path、status、success/error envelope の不整合を修正する。
  - 全 requirement ID が task と fixture / contract note / validation のいずれかに対応していることを確認する。
  - 実ユーザー raw history、絶対パス、secret、token、個人情報が fixture に含まれないことを確認する。
  - 完了時には、契約 fixture set が後続 spec の read-only expectation として使える状態になる。
  - _Depends: 4.1_
  - _Requirements: 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

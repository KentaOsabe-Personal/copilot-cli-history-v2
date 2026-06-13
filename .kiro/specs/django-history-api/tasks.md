# Implementation Plan

- [x] 1. Repository と実行時依存の土台を整える
- [x] 1.1 Atomic な同期開始と終了の repository 契約を追加する
  - 未完了の同期実行がある場合、新しい同期開始が conflict として返り、既存実行の識別子と開始時刻を参照できるようにする。
  - 同期終了では成功、部分劣化、失敗を同じ lifecycle 上で保存できるようにする。
  - fake repository と BigQuery repository のどちらでも同じ start / finish 契約を使える状態になる。
  - _Requirements: 4.4, 4.6, 5.7, 7.4, 7.5_

- [x] 1.2 Raw opt-in に対応した read model 保存内容を整える
  - 同期時の詳細 payload は raw を含められる形で保存し、通常詳細の raw 抑制は API 層に委ねる。
  - 検索 projection には raw JSON 全文を混ぜず、会話 preview、本文、issue 由来の表示用テキストに限定する。
  - 保存済み row から default 詳細と raw 詳細の両方を再現できることが確認できる。
  - _Requirements: 3.4, 3.5, 7.2_

- [x] 1.3 Django History API の設定と依存生成を準備する
  - API 用 app、repository backend、許可 origin、BigQuery integration opt-in を settings から参照できるようにする。
  - settings import 時には BigQuery client を作らず、実 repository は明示利用時にだけ生成する。
  - credentials がない開発環境でも fake repository を使う API テストが実行できる。
  - _Requirements: 6.1, 6.2, 6.4, 7.1, 7.4, 7.5_

- [x] 1.4 API テスト用の fake データと dependency override を整える
  - 一覧、空一覧、degraded、詳細、raw 詳細、not found、sync success / conflict / failure を表せる fake データを用意する。
  - 各 backend test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く規約をテスト追加時に満たす。
  - 後続の API テストが実 BigQuery 接続なしで代表挙動を検証できる。
  - _Requirements: 7.1, 7.5, 7.6_

- [x] 2. HTTP 境界の入力・出力契約を実装する
- [x] 2.1 履歴 API の route、method、preflight 入口を登録する
  - 同期、一覧、詳細、raw opt-in 詳細の対象 URL を Django routing で解決できるようにする。
  - 許可 method は一覧・詳細が GET、同期が POST、preflight が OPTIONS になり、対象外 method は成功扱いにならない。
  - Django test client から対象 endpoint に到達できる。
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 6.3_

- [x] 2.2 一覧 query と raw opt-in query の validation を実装する
  - `from` / `to` の日時解釈、range、`limit` の範囲、`search` の長さと制御文字を検証する。
  - `include_raw=true` だけを raw opt-in として扱い、未指定時は通常詳細として扱う。
  - validation error では field、reason、必要な場合は value を保持した結果が返る。
  - _Requirements: 2.1, 2.2, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 2.3 API response と error envelope の変換を実装する
  - 成功 response は一覧、詳細、同期の既存 presenter contract に沿って HTTP 200 で返す。
  - validation、not found、running sync、root failure、repository failure を status と `error.code`、`error.message`、`error.details` に変換する。
  - frontend が code と status で validation、not found、conflict、service failure を区別できる。
  - _Requirements: 1.5, 3.6, 4.4, 4.5, 4.6, 5.1, 5.7_

- [x] 2.4 Local frontend development 用 CORS response を実装する
  - 設定済み development origin だけに CORS header を返し、wildcard origin は使わない。
  - preflight では対象 method と header が browser から呼び出せる形で返る。
  - auth、admin、server-side session を要求せず stateless な response が得られる。
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 3. 一覧・詳細 API の service behavior を実装する
- [x] 3.1 (P) 保存済み read model からセッション一覧を返す
  - 有効な期間と検索語を repository 条件に変換し、保存済み summary payload を一覧 response の data として返す。
  - 一致なしでは HTTP 200 相当の空 data、count 0、partial_results false を返す。
  - degraded session が含まれる場合は各 session の degraded / issues を保持し、partial_results true を返す。
  - 一覧取得では reader や write operation が呼ばれないことを観測できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - _Boundary: HistoryApiService list flow_

- [x] 3.2 (P) 詳細 payload の raw 抑制と raw opt-in 変換を実装する
  - 通常詳細では `raw_included` が false になり、raw payload fields が通常表示で利用されない値に抑制される。
  - raw opt-in 詳細では `raw_included` が true になり、保存済み raw value が保持される。
  - conversation、activity、timeline、issue など raw 以外の既存 detail shape は変換前後で維持される。
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - _Boundary: DetailPayloadRawFilter_

- [x] 3.3 セッション詳細取得の service behavior を実装する
  - 存在する session ID では repository の detail payload を取得し、raw 指定に応じた data を返す。
  - 存在しない session ID では `session_not_found` に変換できる service result を返す。
  - repository failure は not found と混同されず、service failure として response 層に渡る。
  - _Depends: 3.2_
  - _Requirements: 1.3, 1.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.7_

- [x] 4. 履歴同期 API の service behavior を実装する
- [x] 4.1 同期用 row assembly と件数集計を実装する
  - reader result から保存対象 session row、workspace-only skip、invalid failure、degraded count を組み立てる。
  - sync run row には started / finished 時刻、status、counts、failure / degradation summary を反映する。
  - 同期 response に必要な counts と sync_run meta を service から参照できる。
  - _Requirements: 4.1, 4.2, 4.3, 4.6_

- [x] 4.2 同期成功と部分劣化完了の request 内 orchestration を実装する
  - API request 内で atomic start、reader read、session 保存、sync run finish まで完了させる。
  - 全件成功では HTTP 200 相当の `data.sync_run` と `data.counts` を返せる。
  - degraded session を含む完了では error envelope ではなく成功 response として status / degraded_count に反映される。
  - background job、progress polling、自動 file watch は作成されない。
  - _Depends: 1.1, 4.1_
  - _Requirements: 4.1, 4.2, 4.3, 4.7_

- [x] 4.3 同期 conflict、root failure、保存失敗の error flow を実装する
  - running sync conflict では reader と session 保存を呼ばず、HTTP 409 相当の `history_sync_running` details を返す。
  - 履歴 root が解決または読取できない場合は空成功にせず、root failure を識別できる失敗 response に変換する。
  - 保存失敗では `history_sync_failed` と sync run meta を含む failure result が返る。
  - _Depends: 1.1, 4.1_
  - _Requirements: 4.4, 4.5, 4.6, 5.7_

- [x] 5. Django app と API 境界を統合する
- [x] 5.1 View から validation、service、response、CORS を接続する
  - view は request method、query、CORS、JsonResponse の責務に集中し、raw files や BigQuery client を直接扱わない。
  - 一覧・詳細・同期の service result が status と JSON body に変換されて返る。
  - 対象 API endpoint の成功・失敗 response に CORS header が適用される。
  - _Depends: 2.2, 2.3, 2.4, 3.1, 3.3, 4.2, 4.3_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 6.1, 6.2, 6.3_

- [x] 5.2 Project URLconf と runtime dependency を接続する
  - root URLconf から履歴 API route が include され、既存 health endpoint は維持される。
  - runtime は settings に応じた repository、reader、clock を遅延生成し、tests は fake dependency に差し替えられる。
  - frontend UI、hook、DTO の変更なしに API base URL から対象 endpoint を呼べる状態になる。
  - _Depends: 1.3, 2.1, 5.1_
  - _Requirements: 6.1, 6.4, 6.5, 7.1, 7.5_

- [x] 6. Fake repository による API behavior tests を追加する
- [x] 6.1 (P) route、method、preflight、CORS の request tests を追加する
  - 対象 URL が解決され、許可 method と OPTIONS が期待 status / header を返すことを検証する。
  - allowed origin と disallowed origin の response 差分を検証する。
  - 各 test case の直前に規約コメントがある。
  - _Depends: 5.2_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.3, 6.4, 7.6_
  - _Boundary: Route and CORS tests_

- [x] 6.2 (P) セッション一覧 API の request tests を追加する
  - valid range、search、empty、degraded、read-only call pattern を fake repository で検証する。
  - invalid datetime、invalid range、invalid limit、invalid search が `invalid_session_list_query` と details を返すことを検証する。
  - summary fields と meta.count / partial_results が frontend 互換 shape で観測できる。
  - _Depends: 5.2_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.2, 5.3, 5.4, 5.5, 5.6, 7.1, 7.6_
  - _Boundary: Session list API tests_

- [x] 6.3 (P) セッション詳細 API の request tests を追加する
  - found、default raw suppression、raw opt-in、not found、repository failure を fake repository で検証する。
  - conversation、activity、timeline、degraded、issues が既存 detail contract の shape で返ることを確認する。
  - default response と raw response の差分が raw inclusion に限定されることを観測できる。
  - _Depends: 5.2_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.7, 7.1, 7.6_
  - _Boundary: Session detail API tests_

- [x] 6.4 (P) 履歴同期 API の request tests を追加する
  - success、completed_with_issues、running conflict、root failure、save failure を fake reader / repository で検証する。
  - conflict 時に reader と session 保存が呼ばれず、details に sync_run_id と started_at が入ることを確認する。
  - sync が request 内で完了し、background job や polling の前提がないことを検証する。
  - _Depends: 5.2_
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.1, 7.6_
  - _Boundary: History sync API tests_

- [ ] 7. Contract fixture と integration 入口で互換性を検証する
- [ ] 7.1 Contract fixture scenario と Django response の比較テストを追加する
  - fixture の request method、endpoint、expected status、expected body と API response を比較する。
  - list、detail、raw detail、not found、validation、sync success、sync conflict、sync failure の代表 scenario を fake data で再現する。
  - fixture と API response が一致すれば Rails 互換 contract を機械的に確認できる。
  - _Depends: 6.1, 6.2, 6.3, 6.4_
  - _Requirements: 1.5, 7.1, 7.2, 7.6_

- [ ] 7.2 Contract fixture 差分の診断出力を整える
  - body mismatch では scenario、HTTP status、差分 field path を識別できる失敗メッセージを返す。
  - status mismatch と body mismatch が混ざらず、レビュー担当者が原因箇所を追える。
  - 意図的な fixture drift が発生した場合に、失敗結果から修正対象 scenario を特定できる。
  - _Depends: 7.1_
  - _Requirements: 7.3_

- [ ] 7.3 BigQuery integration opt-in の入口を検証する
  - 明示 opt-in と credentials / dataset が揃う場合だけ実 repository smoke が実行される。
  - credentials がない場合でも fake repository と contract fixture の主要 API 検証は継続する。
  - integration gate の結果から、実接続未設定と実 repository failure を区別できる。
  - _Depends: 1.3, 5.2_
  - _Requirements: 7.4, 7.5_

- [ ] 7.4 Backend quality gate で Django History API の完了状態を確認する
  - backend の test、lint、typecheck が新規 API 層と repository 拡張を含めて通る。
  - 対象 endpoint の成功 response、error response、HTTP status code が contract fixture と照合済みになる。
  - Rails / Django 差分レポート作成、Rails / MySQL stack 削除、frontend UI 変更が完了条件に含まれていないことを確認できる。
  - _Depends: 7.1, 7.2, 7.3_
  - _Requirements: 1.5, 6.5, 7.7_

# Implementation Plan

- [x] 1. 同期時に cwd を保存できるようにする
- [x] 1.1 current session の cwd を DB と一覧 payload に保存する
  - current 形式の raw workspace に cwd がある場合、同期後の保存済み session に同じ cwd が入るようにする。
  - 一覧 API が返す summary payload でも、同じ cwd を `work_context` の値として読めるようにする。
  - cwd がない session では、git root や repository から推測した値を入れない。
  - 検索用本文には cwd を混ぜず、cwd は表示・検索に使える独立した metadata として残す。
  - 完了時には、cwd あり / なしの保存結果をテストで確認できる。
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 4.4_
  - _Boundary: CurrentSessionReader, SessionRecordBuilder_

- [x] 1.2 既存 row の cwd 欠落を明示同期で直せるようにする
  - raw current session には cwd があるのに、保存済み row の cwd または summary payload が空の場合は更新対象にする。
  - source fingerprint が同じでも、cwd の保存状態が古い row は skip せず再生成する。
  - raw に cwd がない session は、同期し直しても cwd なしのまま保つ。
  - 完了時には、明示同期後に DB の cwd と一覧 payload の cwd が raw current session の cwd に揃うことをテストで確認できる。
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.4_
  - _Boundary: HistorySyncService_

- [x] 2. 一覧 API で cwd 検索できるようにする
- [x] 2.1 (P) 既存の検索パラメータだけで cwd 検索も扱う
  - `search` の trim、空白正規化、200 文字上限、制御文字拒否をそのまま使う。
  - cwd 専用 parameter や repository / branch / model filter は追加しない。
  - 無効な検索語は、通常の一覧取得失敗ではなく検索条件エラーとして返る状態を保つ。
  - 完了時には、検索 parameter の有効値・無効値の扱いが既存と変わらないことをテストで確認できる。
  - _Requirements: 3.2, 4.2, 5.5_
  - _Boundary: SessionListParams_

- [x] 2.2 (P) `search` で本文と cwd の両方に一致させる
  - 既存の本文 / preview / issue 検索は維持し、同じ検索語で cwd の部分一致も見るようにする。
  - 日付範囲が指定された場合は、本文一致または cwd 一致した session をさらに日付範囲で絞り込む。
  - `%` と `_` は wildcard ではなく普通の文字として検索する。
  - repository、branch、selected model、git root は今回の検索対象に入れない。
  - 完了時には、本文一致、cwd 一致、日付範囲併用、不一致時の空結果、wildcard 文字の検索をテストで確認できる。
  - _Requirements: 1.2, 1.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.3, 4.5_
  - _Boundary: SessionIndexQuery_

- [x] 2.3 cwd 検索でも既存の一覧 API response を崩さない
  - cwd で検索した場合も、返す summary、meta、degraded、issue 情報の形を変えない。
  - 通常表示と検索表示のどちらも保存済み read model だけを使い、request 中に raw files を直接読まない。
  - cwd に一致しない検索語は、エラーではなく空の一覧として返す。
  - 完了時には、request spec で cwd 検索の成功、空結果、raw reader 非呼び出しを確認できる。
  - _Depends: 2.1, 2.2_
  - _Requirements: 3.1, 3.4, 3.5, 4.5_
  - _Boundary: SessionsController, SessionIndexQuery_

- [x] 3. 一覧カードに cwd を表示する
- [x] 3.1 (P) summary metadata に「実行ディレクトリ」を追加する
  - frontend の summary DTO で cwd を受け取れることを確認し、不足があれば既存 response shape に合わせて補う。
  - cwd がある session では、metadata に「実行ディレクトリ」として cwd を追加する。
  - repository や branch があっても、cwd の表示項目を隠さない。
  - cwd が `null` または空白の場合は、空項目や「不明」を表示しない。
  - 完了時には、metadata 生成テストで cwd 表示、repository / branch との併存、cwd 欠損時の非表示を確認できる。
  - _Requirements: 2.1, 2.2, 2.3, 4.4_
  - _Boundary: sessionApi.types, metadata display helpers_

- [x] 3.2 長い cwd でも一覧カードの表示を崩さない
  - 一覧カードで cwd と repository / branch を同時に読めるようにする。
  - 長い path はカード幅を広げず、折り返して読めるようにする。
  - 既存の preview、表示日時、例外 signal、詳細リンクは維持する。
  - 完了時には、カード表示テストで cwd 表示、長い path の折り返し、既存情報の維持を確認できる。
  - _Depends: 3.1_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - _Boundary: SessionSummaryCard_

- [x] 4. 検索 UI で cwd も検索対象だと分かるようにする
- [x] 4.1 (P) 検索フォームの説明に実行ディレクトリを追加する
  - 検索対象の説明を、会話本文、preview、issue、実行ディレクトリが対象だと分かる文言にする。
  - 現在の検索語と日付範囲を確認できる条件表示は維持する。
  - backend から返る検索条件エラーは、通常の取得失敗と区別して表示する。
  - 完了時には、フォーム表示テストで説明文、条件表示、検索条件エラー表示を確認できる。
  - _Requirements: 5.1, 5.4, 5.5_
  - _Boundary: SessionSearchForm_

- [x] 4.2 (P) cwd 検索の適用・解除でも日付範囲を保つ
  - cwd 由来の検索語を適用しても、現在の日付範囲を同じ request 条件として残す。
  - 検索語を解除しても、日付範囲は維持したまま検索語なしの一覧へ戻す。
  - 古い request の結果が、別条件の一覧として表示されない既存の動きを維持する。
  - 完了時には、hook または条件 helper のテストで検索適用・解除後も同じ日付範囲が残ることを確認できる。
  - _Requirements: 5.2, 5.3, 5.4_
  - _Boundary: useSessionIndex, sessionIndexCriteria_

- [ ] 5. 同期・検索・表示をまとめて確認する
- [ ] 5.1 backend の利用者フローを通して確認する
  - current session を明示同期した後、DB と一覧 API payload に同じ cwd が入ることを確認する。
  - cwd の一部文字列で一覧検索したとき、対象 session が既存 response shape のまま返ることを確認する。
  - cwd がない session に推測値が付かず、cwd 検索にも一致しないことを確認する。
  - 完了時には、backend 統合テストで同期保存、cwd 検索、欠損時の非推測、response shape 維持を一連で確認できる。
  - _Depends: 1.2, 2.3_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.1, 3.5, 4.4, 4.5_
  - _Boundary: HistorySyncService, SessionIndexQuery, SessionsController_

- [ ] 5.2 frontend の一覧表示と検索フローを通して確認する
  - cwd を持つ session summary が一覧カードに表示され、repository / branch と preview も併存することを確認する。
  - cwd 由来の検索語を適用・解除しても、日付範囲と条件表示が保たれることを確認する。
  - 検索条件エラーと通常の一覧取得失敗が区別され、利用者が条件を見直せる表示になることを確認する。
  - 完了時には、frontend の component / hook / page レベルの回帰テストで一覧表示、検索条件維持、検索条件エラー表示を確認できる。
  - _Depends: 3.2, 4.1, 4.2_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5_
  - _Boundary: SessionIndexPage, SessionSummaryCard, SessionSearchForm, useSessionIndex_

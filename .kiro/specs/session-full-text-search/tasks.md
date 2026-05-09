# Implementation Plan

- [x] 1. 保存済みセッションの検索対象を read model に追加する
- [x] 1.1 検索対象テキストを保存できる永続化契約を整える
  - セッション単位の read model に検索対象テキストを保持できるようにする。
  - 既存レコードは空文字の検索対象を持てるが、未設定値は保存できない契約にする。
  - 検索対象テキストは再生成可能な補助情報として扱い、raw files を一次ソースとする方針を変えない。
  - 完了時には、既存レコードと新規レコードのどちらも検索対象テキストを持つ状態で保存できる。
  - _Requirements: 1.1, 1.5, 5.5_

- [x] 1.2 検索対象テキストを保存 payload と履歴メタ情報から生成する
  - 会話本文、会話要約、tool call、activity、issue、作業コンテキスト、選択モデルを検索対象へ含める。
  - current 形式と legacy 形式の差分を保存 payload の範囲で吸収し、同じ検索体験で扱える文字列を生成する。
  - degraded 状態や issue 情報がある場合も、読み取れた範囲の本文と issue code / message を検索対象から失わせない。
  - 検索対象外の raw payload、source fingerprint、内部 timestamp は含めない。
  - 完了時には、生成結果が正規化済み文字列として返り、空セッションでも nil ではなく空文字を返すことをテストで確認できる。
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.2, 5.5_

- [x] 1.3 明示同期で検索 projection 未作成の既存行を更新対象にする
  - source fingerprint が不変でも、検索対象テキストが未作成の既存行は保存属性を再生成して更新する。
  - 検索対象テキストが作成済みで fingerprint も不変の行は、既存どおり skip できるようにする。
  - root failure、degraded handling、同期中 lock、同期結果 count の既存挙動を維持する。
  - 完了時には、手動同期後に保存済みセッションが一覧検索の対象になることを同期テストで確認できる。
  - _Requirements: 1.1, 1.4, 1.5, 5.5_

- [x] 2. セッション一覧 API に検索条件を追加する
- [x] 2.1 検索語を一覧条件として正規化・検証する
  - 検索語は任意条件として受け取り、trim と空白正規化後の空文字は未指定として扱う。
  - 長すぎる検索語や表示不能な制御文字は、一覧取得前に client error として区別できるようにする。
  - 検索語なしの一覧取得では、既存の日付範囲と件数条件だけで対象を決める。
  - 完了時には、blank、trim、最大長超過、制御文字、日付範囲との同時指定が条件 parser のテストで確認できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 5.1_

- [x] 2.2 保存済み検索対象と日付範囲を合成して一覧を取得する
  - 検索語がある場合だけ、保存済み検索対象テキストへの literal substring 条件を追加する。
  - `%`、`_`、escape 文字は wildcard ではなく利用者が入力した文字として扱う。
  - 日付範囲、表示日時順、tie-break、limit、degraded / issue payload、件数 meta の既存契約を維持する。
  - 検索一致が 0 件の場合は失敗ではなく、空の data と件数 0 の meta を返せるようにする。
  - 完了時には、検索単独、日付範囲との併用、検索語なし、literal 記号一致、空成功を query テストで確認できる。
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.5, 5.6_

- [x] 2.3 HTTP 境界で検索条件と既存 response shape を接続する
  - 一覧 request の検索条件を検証し、不正検索語は成功応答と区別できる error envelope で返す。
  - 検索条件を含む成功応答でも、既存の一覧 response shape、件数 meta、degraded 状態、issue 情報を維持する。
  - 一覧 API は read-only GET の境界に留まり、検索時にも raw files を直接読まない。
  - 完了時には、検索条件付き request の 200、空成功、400 client error、raw reader 非呼び出しを request spec で確認できる。
  - _Depends: 2.1, 2.2_
  - _Requirements: 2.4, 2.5, 2.6, 4.5, 5.5, 5.6_

- [x] 3. フロントエンドの検索 criteria と取得 lifecycle を追加する
- [x] 3.1 日付範囲と検索語を 1 つの一覧 criteria として扱う
  - 現在の日付範囲と検索語から、一覧 API query、criteria key、表示ラベルを同じ規則で生成する。
  - blank 検索語は query に含めず、検索語ありの場合だけ一覧条件として送信する。
  - frontend validation は backend と同じ最大長と制御文字ルールで検索語を判定する。
  - 完了時には、query 直列化、criteria key、表示ラベル、blank omission、不正検索語が presentation / API client のテストで固定される。
  - _Requirements: 3.2, 3.3, 3.4, 4.1, 4.2, 4.4, 5.1_

- [x] 3.2 一覧取得 hook が検索適用・解除・再取得を管理する
  - 初期 criteria は既存の既定日付範囲と空検索語で開始する。
  - 検索適用と解除は現在の日付範囲を維持し、日付範囲適用は現在の検索語を維持する。
  - 同期後の再取得は latest applied criteria を使い、検索語と日付範囲を維持する。
  - request id、abort、criteria key によって、別検索語の遅延応答を current result として採用しない。
  - 完了時には、検索適用、解除、same-criteria refresh、sync 後 reload、stale response 防止を hook テストで確認できる。
  - _Depends: 3.1_
  - _Requirements: 3.2, 3.3, 3.5, 3.6, 4.1, 4.4_

- [x] 3.3 (P) 検索語入力、適用、解除、条件エラー表示を提供する
  - 一覧画面から検索語を入力し、submit または Enter で適用できる操作を用意する。
  - 適用中の検索語がある場合は解除操作を表示し、解除時に日付範囲を変えない。
  - frontend validation error と backend 由来の検索条件 error を、通常の一覧取得失敗とは分けて表示する。
  - 完了時には、入力、適用、Enter submit、解除、invalid message、backend search error 表示を component テストで確認できる。
  - _Depends: 3.1_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.4_
  - _Boundary: SessionSearchForm_

- [x] 3.4 (P) 検索空状態と通常空状態を区別する
  - 検索語ありの 0 件は、通常の空一覧や取得失敗とは別の検索空状態として表示する。
  - 検索空状態でも現在の検索語と日付範囲を確認でき、解除や条件見直しに進める。
  - read-only 体験を維持し、検索空状態や取得失敗で編集・削除・共有操作を提示しない。
  - 完了時には、検索空、日付条件だけの空、generic error の表示差分を component テストで確認できる。
  - _Depends: 3.1_
  - _Requirements: 2.5, 3.4, 4.3, 4.5, 5.4, 5.6_
  - _Boundary: SessionEmptyState_

- [x] 4. 一覧画面へ検索体験を統合する
- [x] 4.1 日付条件と検索条件を一覧画面の適用済み条件として表示・操作する
  - 一覧画面で検索フォーム、日付フォーム、一覧、状態表示を同じ applied criteria に結び付ける。
  - 検索語を適用した結果では、現在の検索語と日付範囲に基づく結果であることを画面上で確認できる。
  - 検索条件付き loading は、検索条件を含む一覧取得中であることを通常 loading と区別して示す。
  - repository / branch / model 専用 filter、並び替え UI、pagination、詳細画面内検索は追加しない。
  - 完了時には、検索適用、検索結果 label、検索 loading、日付条件維持が page テストで確認できる。
  - _Depends: 3.2, 3.3, 3.4_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 5.1, 5.3, 5.6_

- [x] 4.2 同期・失敗・条件切替後も read-only 検索体験を維持する
  - 手動同期後の一覧再取得は、適用中の検索語と日付範囲を維持したまま結果を更新する。
  - 別検索語への切替中に、直前の別検索語の一覧を新しい条件の確定結果として表示し続けない。
  - 検索条件の client error は条件修正へ誘導し、network / server failure は read-only の再試行または条件見直しに留める。
  - 履歴編集、削除、共有、認証、認可、自動同期の操作をこの feature で追加しない。
  - 完了時には、sync 後 refresh、条件切替、検索条件 error、generic error、read-only scope が page 統合テストで確認できる。
  - _Depends: 4.1_
  - _Requirements: 3.5, 3.6, 4.4, 4.5, 5.3, 5.4, 5.6_

- [x] 5. 検索 feature の contract と回帰を固定する
- [x] 5.1 backend の検索対象生成、同期、一覧 API contract を検証する
  - 検索対象に含める field、current / legacy、degraded / issue、検索対象外 field を unit spec で固定する。
  - 検索 projection 未作成行の同期更新と、作成済み行の skip 維持を sync spec で固定する。
  - 検索語と日付範囲の合成、response shape 維持、empty success、invalid search を request / query spec で固定する。
  - 完了時には、backend の検索関連 spec が保存済み read model 基準で通り、raw files 直接検索を期待しない状態になる。
  - _Depends: 1.3, 2.3_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.2, 5.5, 5.6_

- [x] 5.2 frontend の検索 criteria、状態管理、表示状態を検証する
  - criteria helper、API serialization、hook、検索フォーム、空状態、一覧ページの検索体験をテストで固定する。
  - 検索中、検索結果、検索空、検索条件 error、通常空、generic error の区別を確認する。
  - 日付範囲との併用、検索解除、同期後再取得、stale response 防止を同じ test suite で確認する。
  - 完了時には、frontend の検索関連テストが read-only の一覧探索に閉じた体験を固定している。
  - _Depends: 4.2_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.3, 5.4, 5.6_

- [x] 5.3 標準検証で backend / frontend の回帰がないことを確認する
  - backend の対象 spec と品質確認コマンドを Docker Compose 標準環境で実行する。
  - frontend の lint、build、検索関連 test を Docker Compose 標準環境で実行する。
  - 新規 gem、外部検索サービス、semantic search、ベクトル検索、検索結果スコアリング、検索語ハイライトを導入していないことを確認する。
  - 完了時には、実行した検証コマンドと結果を implementation handoff で報告できる。
  - _Depends: 5.1, 5.2_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

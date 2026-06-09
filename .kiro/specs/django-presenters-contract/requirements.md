# Requirements Document

## Introduction
この Spec は、Django 移行後もフロントエンドから見える JSON レスポンスを Rails 版と一致させるための Presenter 契約を定義する。対象は、セッション一覧、セッション詳細、履歴同期結果、共通エラー形式である。

目的は、reader、repository、API handler の実装差分に埋もれがちな「レスポンスの形の違い」を Presenter 層で検出できるようにすることである。Python 側の normalized session と sync result を入力にして、既存の `api-contract-fixtures` と同じレスポンス本文を作れる状態を目指す。

この Spec は「何を返すべきか」を決める。raw file の読み取り、保存処理、request routing、status code の最終判定、UI 表示変更は扱わない。

## Boundary Context
- **In scope**: セッション一覧の要約レスポンス、セッション詳細レスポンス、履歴同期レスポンス、共通エラー形式、raw payload を含める場合と含めない場合の表現、degraded / partial issue の表示位置、fixture 比較による契約検証。
- **Out of scope**: raw file parsing、request endpoint / handler 実装、status routing の最終決定、repository query / upsert、frontend UI 改修、旧 backend stack 削除。
- **Adjacent expectations**: `api-contract-fixtures` は期待レスポンスの正本として参照する。`copilot-history-python-reader` は正規化済み session と issue 情報を提供する。後続の repository / API Spec は、この Presenter 契約で固定されたレスポンス本文を利用する。

## Requirements

### Requirement 1: Rails 互換レスポンス契約
**Objective:** As a backend maintainer, I want Presenter が返すレスポンス本文を既存 fixture と一致させる, so that backend 切替時の JSON 形状差分を早期に検出できる

#### Acceptance Criteria
1. When Presenter が一覧、詳細、同期、エラーのレスポンス本文を生成する, the Copilot History Presenter Contract shall `api-contract-fixtures` の該当レスポンス本文と同じ top-level envelope を返す
2. When fixture が成功レスポンスを示す, the Copilot History Presenter Contract shall top-level `data` と必要な `meta` を fixture と同じ形で返す
3. When fixture がエラーレスポンスを示す, the Copilot History Presenter Contract shall top-level `error.code`、`error.message`、`error.details` を fixture と同じ形で返す
4. The Copilot History Presenter Contract shall frontend の既存 session API 型で表現されるフィールド名、null 許容、配列とオブジェクトの入れ子構造を維持する
5. The Copilot History Presenter Contract shall request routing、status の最終判定、保存用データ形状、frontend rendering の責務を含めない

### Requirement 2: セッション一覧の要約レスポンス
**Objective:** As a session list user, I want 一覧レスポンスが既存画面に必要な要約情報を同じ形で返す, so that backend が切り替わっても一覧画面の表示契約が変わらない

#### Acceptance Criteria
1. When 正規化済み session の一覧が渡される, the Copilot History Presenter Contract shall 各 session を `id`、`source_format`、`created_at`、`updated_at`、`work_context`、`selected_model`、`source_state`、`event_count`、`message_snapshot_count`、`conversation_summary`、`degraded`、`issues` を持つ要約レスポンスへ変換する
2. When current 形式と legacy 形式の session が同じ一覧に含まれる, the Copilot History Presenter Contract shall 両方の session を同じ要約 schema で返す
3. When session が会話 message を持つ, the Copilot History Presenter Contract shall `conversation_summary.has_conversation`、`message_count`、`preview`、`activity_count` を既存契約と同じ意味で返す
4. When session が会話 message を持たない, the Copilot History Presenter Contract shall 空の会話状態を fixture と同じ null、件数、真偽値の表現で返す
5. When 一覧レスポンス本文が生成される, the Copilot History Presenter Contract shall `meta.count` に返却 session 数を含め、degraded session が含まれる場合は `meta.partial_results` を true にする

### Requirement 3: セッション詳細レスポンスと raw payload 表示
**Objective:** As a session detail user, I want 詳細レスポンスが会話、activity、timeline、raw payload の有無を同じ形で返す, so that 詳細画面が Rails 版と同じ契約で動作する

#### Acceptance Criteria
1. When 正規化済み session detail が渡される, the Copilot History Presenter Contract shall 詳細レスポンスに session header、`message_snapshots`、`conversation`、`activity`、`timeline` を fixture と同じ入れ子構造で含める
2. When timeline event が message、detail、unknown のいずれかとして渡される, the Copilot History Presenter Contract shall `sequence`、`kind`、`mapping_status`、`raw_type`、`occurred_at`、`role`、`content`、`tool_calls`、`detail`、`degraded`、`issues` を既存の詳細 schema で返す
3. When activity entry が生成される, the Copilot History Presenter Contract shall `sequence`、`category`、`title`、`summary`、`raw_type`、`mapping_status`、`occurred_at`、`source_path`、`raw_available`、`degraded`、`issues` を既存の activity schema で返す
4. When raw payload の表示が要求されない, the Copilot History Presenter Contract shall `raw_included` を false にし、timeline、activity、message snapshot の `raw_payload` を null として返す
5. When raw payload の表示が明示的に要求される, the Copilot History Presenter Contract shall `raw_included` を true にし、raw payload が存在する timeline、activity、message snapshot に fixture と同じ raw value を返す

### Requirement 4: degraded / partial issue の表示
**Objective:** As a user investigating broken history data, I want degraded 状態と issue が既存画面と同じ場所に返る, so that 読めた範囲と破損原因を backend 差分なく確認できる

#### Acceptance Criteria
1. When session 全体に関する issue が渡される, the Copilot History Presenter Contract shall 詳細レスポンスの session `issues` に `scope: "session"` と `event_sequence: null` を含む issue envelope を返す
2. When event に関する issue が渡される, the Copilot History Presenter Contract shall 対象 timeline event と conversation / activity entry の `issues` に `scope: "event"` と対象 `event_sequence` を含む issue envelope を返す
3. When session が issue を 1 件以上持つ, the Copilot History Presenter Contract shall 要約レスポンスと詳細レスポンスの `degraded` を true にする
4. When event または projection entry が issue を持つ, the Copilot History Presenter Contract shall 対象 entry の `degraded` を true にし、他の entry の degraded 状態を変更しない
5. If partial mapping または unknown event が存在する, then the Copilot History Presenter Contract shall 読み取れた field を保持し、該当 issue を既存 issue schema で返す

### Requirement 5: 履歴同期レスポンス
**Objective:** As a user running explicit history sync, I want 同期結果が既存レスポンスと同じ形で返る, so that 同期 UI が成功、部分劣化、競合、失敗を同じ契約で扱える

#### Acceptance Criteria
1. When sync result が succeeded を示す, the Copilot History Presenter Contract shall top-level `data.sync_run` と `data.counts` を含む成功レスポンスを返す
2. When sync result が completed_with_issues を示す, the Copilot History Presenter Contract shall error envelope ではなく成功レスポンスを返し、`sync_run.status` と `counts.degraded_count` に部分劣化を反映する
3. When sync result が running conflict を示す, the Copilot History Presenter Contract shall `history_sync_running` code、既存 running run の id、started_at を含む error envelope を返す
4. When sync result が root failure を示す, the Copilot History Presenter Contract shall upstream failure code、message、path を含む error envelope と sync run meta を返す
5. When sync result が persistence failure を示す, the Copilot History Presenter Contract shall `history_sync_failed` code、failure details、sync run meta、counts を含む error envelope を返す

### Requirement 6: 共通エラー形式
**Objective:** As a frontend error handler, I want Presenter のエラーが同じ envelope で返る, so that not found、validation、root failure、sync conflict を同じ client contract で扱える

#### Acceptance Criteria
1. When session lookup が対象 session を見つけられない, the Copilot History Presenter Contract shall `session_not_found` code、固定 message、対象 `session_id` を含む error envelope を返す
2. When session list query validation が失敗する, the Copilot History Presenter Contract shall validation result の code、message、details を保持した error envelope を返す
3. When history root failure が渡される, the Copilot History Presenter Contract shall root failure code、message、対象 path を保持した error envelope を返す
4. The Copilot History Presenter Contract shall error envelope の top-level key を `error` に固定し、success envelope と混在させない
5. The Copilot History Presenter Contract shall error `details` を object として返し、空でない既知 context がある場合は fixture と同じ key で保持する

### Requirement 7: 契約検証と隣接範囲
**Objective:** As a maintainer validating backend parity, I want Presenter 出力を fixture と自動比較できる, so that API、repository、frontend の変更に混ぜずに契約差分を検出できる

#### Acceptance Criteria
1. When contract tests が実行される, the Copilot History Presenter Contract shall `api-contract-fixtures` の一覧、詳細、raw 付き詳細、同期、エラーの代表 fixture と生成レスポンス本文を比較できる
2. When fixture と生成レスポンス本文に差分がある, the Copilot History Presenter Contract shall 差分のある scenario と field path を特定できる検証結果を返す
3. When Presenter contract の test case が追加または更新される, the Copilot History Presenter Contract shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを持つ
4. The Copilot History Presenter Contract shall raw reader の正規化結果を入力として扱い、raw file parsing の成否判定を Presenter の完了条件に含めない
5. The Copilot History Presenter Contract shall 永続化 repository、request handler、frontend component の変更を完了条件に含めない

# 要件ドキュメント

## 導入

この spec でやることは、**Python backend でローカルの Copilot CLI 履歴ファイルからセッションを取得し、後続 API が使える正規化済みセッションに変換すること**である。

具体的には、current `session-state` と legacy `history-session-state` の両方を読み、セッション ID、作業ディレクトリ、時刻、選択 model、会話本文、tool / system などの activity、読取 issue を同じ形で返せるようにする。Rails 版 `backend/lib/copilot_history/` の reader / normalizer / projection と同等の入力データを Python 側に用意し、Django presenter、BigQuery 保存、HTTP API は後続 spec に分ける。

つまり、この spec は「画面や API の session list/detail を作る」spec ではなく、その手前の「raw 履歴ファイルから session data を読む」spec である。

## 境界コンテキスト

- **In scope**: 履歴ルートから session file を見つけること、current `session-state` を読むこと、legacy `history-session-state` を読むこと、raw event を会話 / activity / unknown に整理すること、読めた session と読めなかった理由を返すこと、検索用テキストの元になる情報を作ること、単体テストで検証すること。
- **Out of scope**: session list/detail API response の最終形、HTTP error envelope、BigQuery への保存、同期 endpoint、frontend 表示、Rails / MySQL 削除、semantic search、Copilot CLI の raw file format 変更。
- **Adjacent expectations**: `django-backend-foundation` は Python backend の実行・検証入口を提供する。`api-contract-fixtures` と現行 Rails 実装は互換期待値の参照元である。後続の `django-presenters-contract`、`bigquery-session-repository`、`django-history-api` は、この spec が返す normalized session と issue 情報を入力として利用する。

## 要件

### Requirement 1: 履歴ルートから session file を見つける

**Objective:** As a 移行開発者, I want Copilot CLI 履歴ルートから読取対象 session を一貫して発見したい, so that current / legacy の保存形式差分を後続処理へ漏らさずに扱える

#### Acceptance Criteria

1. When 履歴ルートの読取が要求されたとき, the Copilot History Python Reader shall raw files を Copilot CLI 履歴の一次ソースとして扱う。
2. When current 形式と legacy 形式の session source が同じ履歴ルートに存在するとき, the Copilot History Python Reader shall 両方を読取対象として列挙できる結果を返す。
3. When session source が列挙されるとき, the Copilot History Python Reader shall 各 source の session id、source format、raw file location、利用可能な metadata を後続処理が識別できる形で示す。
4. If 履歴ルートが存在しない、参照できない、または directory として扱えないとき, the Copilot History Python Reader shall session 単位の成功結果と区別できる root failure を返す。
5. The Copilot History Python Reader shall raw file の発見と読取をローカル履歴参照に限定し、外部送信や自動監視をこの spec の対象に含めない。

### Requirement 2: Current 形式の session を読む

**Objective:** As a 移行開発者, I want current `session-state` の session を normalized session の入力として読める, so that 現行 Copilot CLI の履歴を Rails 互換の後続処理へ渡せる

#### Acceptance Criteria

1. When current `session-state/<session-id>` が読取対象になるとき, the Copilot History Python Reader shall workspace metadata と event log を同じ session に属する raw source として扱う。
2. When current workspace metadata が利用可能なとき, the Copilot History Python Reader shall session id、作業ディレクトリ、repository context、作成時刻、更新時刻、選択 model を normalized session で参照できる情報として返す。
3. When current event log が利用可能なとき, the Copilot History Python Reader shall event の出現順を保持した normalized event sequence を返す。
4. If current workspace metadata が欠損または解釈不能なとき, the Copilot History Python Reader shall その session を正常 session と区別できる issue 付き結果として扱う。
5. If current event log に解釈不能な行または部分的にしか解釈できない event が含まれるとき, the Copilot History Python Reader shall 読める event を保持し、解釈不能箇所を session degraded issue として示す。
6. The Copilot History Python Reader shall current session の読取によって legacy session の読取期待を後退させない。

### Requirement 3: Legacy 形式の session を読む

**Objective:** As a 移行開発者, I want legacy `history-session-state` の session を current session と同じ normalized contract で扱いたい, so that 保存形式の移行期間でも履歴参照を維持できる

#### Acceptance Criteria

1. When legacy `history-session-state` の JSON session が存在するとき, the Copilot History Python Reader shall legacy session を読取対象として扱う。
2. When legacy session が読み取られるとき, the Copilot History Python Reader shall session id、開始時刻、会話 message、timeline、選択 model から得られる情報を normalized session へ対応付ける。
3. When legacy session と current session が同じ一覧に含まれるとき, the Copilot History Python Reader shall 後続処理が同じ種類の normalized session として扱える結果を返す。
4. If legacy JSON が欠損、空、または解釈不能なとき, the Copilot History Python Reader shall 他の正常 session の読取を継続し、対象 session の degraded issue または read failure を識別できるようにする。
5. The Copilot History Python Reader shall legacy raw payload 由来の情報を、current 形式に存在しない項目であっても追跡可能な範囲で保持する。

### Requirement 4: Raw event を共通の session data に変換する

**Objective:** As a 後続 spec の実装者, I want raw event を安定した normalized session contract で受け取りたい, so that presenter、repository、API の差分原因を reader 移植から切り分けられる

#### Acceptance Criteria

1. When raw event が既知の会話 event、tool event、system event、または activity event として解釈できるとき, the Copilot History Python Reader shall normalized event に event kind、role、本文、発生時刻、tool call 情報、raw traceability を含める。
2. When raw event が既知の型に完全一致しないとき, the Copilot History Python Reader shall unknown event として分類し、raw content を失わずに保持する。
3. When event の一部属性だけが解釈できるとき, the Copilot History Python Reader shall 解釈済み属性と raw content の両方を後続処理が参照できるようにする。
4. The Copilot History Python Reader shall normalized session に source format、work context、selected model、source timestamps、event count、degraded state、issue list を含める。
5. The Copilot History Python Reader shall normalized session の contract を HTTP response shape、保存 schema、または frontend 表示の最終形と同一視しない。

### Requirement 5: 会話・activity・検索用テキストの元データを作る

**Objective:** As a 後続 spec の実装者, I want normalized session から会話、activity、検索用テキストの基礎情報を得たい, so that API presenter と read model 保存が同じ入力を再利用できる

#### Acceptance Criteria

1. When normalized session に user または assistant の非空本文 event が含まれるとき, the Copilot History Python Reader shall source order を保った conversation entry を生成できる情報を返す。
2. If assistant event が本文を持たず tool request のみを含むとき, the Copilot History Python Reader shall その event を空の assistant conversation entry として扱わず、必要な tool context を activity または付帯情報として追跡できるようにする。
3. When normalized session に system event、tool execution、hook、skill、unknown event、または非会話 event が含まれるとき, the Copilot History Python Reader shall それらを conversation と区別できる activity entry として示す。
4. When conversation summary が生成されるとき, the Copilot History Python Reader shall message count、preview、empty reason を後続処理が参照できる情報として返す。
5. When search projection の基礎情報が要求されるとき, the Copilot History Python Reader shall 会話本文、preview、issue 由来の検索対象テキストを後続の read model 更新で利用できる形にまとめる。
6. The Copilot History Python Reader shall semantic search、ranking、外部 index 更新をこの spec の対象に含めない。

### Requirement 6: 読めない session と対象外責務を明確にする

**Objective:** As a レビュー担当者, I want reader 移植の成功、部分劣化、対象外責務を明確に判定したい, so that 後続の API / repository 実装と混同せずにレビューできる

#### Acceptance Criteria

1. If session の一部 raw file または event だけが読めないとき, the Copilot History Python Reader shall 読めた範囲の normalized session と session degraded issue を同時に返す。
2. If 履歴ルート全体が読めないとき, the Copilot History Python Reader shall session degraded ではなく root failure として識別できる結果を返す。
3. When Rails 由来 fixture または API contract fixture と比較されるとき, the Copilot History Python Reader shall current / legacy の normalized session、conversation projection、activity projection、issue 表現について互換性を検証できる結果を提供する。
4. Where tests are added or updated for this spec, the Copilot History Python Reader shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを残す project rule に従う。
5. The Copilot History Python Reader shall summary / detail presenter、error envelope、BigQuery 保存、HTTP request / response handling、frontend 表示、Rails / MySQL 削除をこの spec の完了条件に含めない。

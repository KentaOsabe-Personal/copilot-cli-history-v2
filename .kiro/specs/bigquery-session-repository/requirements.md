# 要件ドキュメント

## 導入

この spec は、Django API が BigQuery read model を参照・更新するための session repository 契約を定義する。対象利用者は、Django 側の session list/detail API、明示同期処理、検証コードを実装する開発者である。

BigQuery read model は Copilot CLI raw files の正本ではなく、明示同期で再生成できる補助層として扱う。この repository は、保存済み session の一覧検索、session ID による詳細取得、同期結果の一括保存、同期実行履歴の保存、費用を意識した実行制御、実接続なしでの単体検証を提供する。Django endpoint、raw file reader、schema 初期化、Rails / MySQL 削除はこの spec の完了条件に含めない。

## 境界コンテキスト

- **In scope**: repository interface、BigQuery read model への session list query、session detail lookup、日付 range / 検索語 / limit / session_id 条件、同期用の一括保存、sync run 保存、dry run / maximum bytes billed などの cost guardrail、fake repository と repository contract test。
- **Out of scope**: Django API endpoint、request / response presenter の再定義、raw file reader 移植、BigQuery schema 初期化、Rails / Django parity report、Rails / MySQL 削除、BigQuery を Django ORM として扱うこと、高度な Search Index / semantic search、background job 化、GCP production operation design。
- **Adjacent expectations**: `bigquery-read-model-schema` は dataset / table / schema / fake row contract を提供する。`django-presenters-contract` は保存・返却する summary / detail payload の互換契約を提供する。`django-history-api` はこの repository を使って HTTP endpoint を提供する。`react-django-runtime-validation` は後続で Rails 由来 fixture と React + Django runtime による切替確認を行う。

## 要件

### Requirement 1: Repository 契約と read model 境界

**Objective:** As a Django backend 開発者, I want session repository が read model 参照と同期保存の境界を明確に提供する, so that API と同期処理が BigQuery の詳細に直接依存せず同じ契約を利用できる。

#### 受け入れ基準

1. The BigQuery Session Repository shall 保存済み session の一覧取得、session 詳細取得、session 同期保存、sync run 保存を同じ read model 契約として提供する。
2. The BigQuery Session Repository shall raw files を一次ソースとして扱うプロダクト方針を変更せず、保存済み read model を再生成可能な参照先として扱う。
3. The BigQuery Session Repository shall `bigquery-read-model-schema` で定義された `copilot_sessions` と `history_sync_runs` の保存契約に適合する data を扱う。
4. The BigQuery Session Repository shall `django-presenters-contract` で定義された summary payload と detail payload の shape を repository 内で別 shape に再定義しない。
5. The BigQuery Session Repository shall Django API endpoint、HTTP status 判定、frontend 表示、raw file parsing、schema 初期化をこの feature の責務として提供しない。

### Requirement 2: セッション一覧 query

**Objective:** As a セッション履歴を閲覧する利用者, I want 保存済み read model から日付範囲と検索条件に合うセッション一覧が返る, so that BigQuery 移行後も既存の一覧探索を継続できる。

#### 受け入れ基準

1. When 一覧条件として日付 range が指定される, the BigQuery Session Repository shall 履歴由来の表示日時が指定範囲に含まれる session だけを一覧候補にする。
2. While 履歴由来の更新日時が存在する session を一覧条件で判定するとき, the BigQuery Session Repository shall 更新日時を表示日時として扱う。
3. While 履歴由来の更新日時が欠落し、履歴由来の作成日時が存在する session を一覧条件で判定するとき, the BigQuery Session Repository shall 作成日時を表示日時として扱う。
4. If 履歴由来の更新日時と作成日時がどちらも欠落している session が存在するとき, the BigQuery Session Repository shall その session を日付 range に一致する一覧候補として扱わない。
5. When 一覧条件として検索語が指定される, the BigQuery Session Repository shall 保存済み検索対象または作業ディレクトリ情報に検索語が一致する session だけを一覧候補にする。
6. When 日付 range と検索語が同時に指定される, the BigQuery Session Repository shall 両方の条件に一致する session だけを一覧候補にする。
7. When 一覧結果を返す, the BigQuery Session Repository shall 表示日時の降順、同一表示日時では session ID 昇順の安定した順序で summary payload を返す。
8. When 正の limit が指定される, the BigQuery Session Repository shall 条件と並び順を適用した後、指定件数を超えない summary payload を返す。
9. If 一覧条件に一致する session が存在しない, the BigQuery Session Repository shall 失敗ではなく空の一覧結果として返す。

### Requirement 3: セッション詳細 lookup

**Objective:** As a 過去セッションを読み返す利用者, I want session ID で保存済み detail payload を取得できる, so that raw files の再読取なしで詳細画面を開ける。

#### 受け入れ基準

1. When 存在する session ID が指定される, the BigQuery Session Repository shall 対象 session の保存済み detail payload を返す。
2. When detail payload を返す, the BigQuery Session Repository shall 保存済み payload の header、message snapshots、conversation、activity、timeline、degraded 状態、issue 情報を失わせない。
3. When current 形式または legacy 形式の session が指定される, the BigQuery Session Repository shall source format にかかわらず同じ lookup 契約で detail payload を返す。
4. If 指定された session ID が保存済み read model に存在しない, the BigQuery Session Repository shall not found として識別できる結果を返す。
5. The BigQuery Session Repository shall detail lookup のために raw files を直接読み取らない。

### Requirement 4: 同期保存と sync run 記録

**Objective:** As a 履歴同期処理の実装者, I want 読み取った session 群と同期結果を read model に一括反映できる, so that BigQuery の制約と既存同期契約を両立できる。

#### 受け入れ基準

1. When 明示同期処理が保存対象 session 群を渡す, the BigQuery Session Repository shall 各 session を保存済み read model の最新同期結果として参照できる状態にする。
2. When 新しい session ID の session が保存対象に含まれる, the BigQuery Session Repository shall その session を新規保存として扱える結果を返す。
3. When 既存 session ID の session が保存対象に含まれる, the BigQuery Session Repository shall その session を重複させず更新保存として扱える結果を返す。
4. When 保存対象 session の source fingerprint と保存済み fingerprint が一致し、検索 projection が現行契約に一致するとき, the BigQuery Session Repository shall その session を skip として扱える結果を返す。
5. When workspace only の session が保存対象候補に含まれる, the BigQuery Session Repository shall 表示用 read model に保存しない session として扱える結果を返す。
6. When degraded session が保存対象になる, the BigQuery Session Repository shall degraded 状態と issue 情報を後続表示が識別できる payload として保持する。
7. When 同期保存が完了する, the BigQuery Session Repository shall processed、inserted、updated、saved、skipped、failed、degraded の件数を後続処理が識別できる結果として返す。
8. When sync run が開始または終了する, the BigQuery Session Repository shall running、succeeded、failed、completed_with_issues の状態と開始・終了時刻、件数、失敗または劣化の概要を保存できる。
9. While 未完了の sync run が存在するとき, the BigQuery Session Repository shall 新しい同期処理が二重実行中であることを識別できる状態を提供する。

### Requirement 5: BigQuery 実行制御と cost guardrail

**Objective:** As an 運用者, I want repository の BigQuery 実行が日付条件と費用上限を尊重する, so that 一覧取得や同期保存で意図しない scan cost を避けられる。

#### 受け入れ基準

1. When session list query が実行される, the BigQuery Session Repository shall `copilot_sessions` の partition 前提に合う日付条件を利用して一覧候補を絞り込む。
2. If session list query に日付 range が指定されない場合, the BigQuery Session Repository shall 呼び出し側が既定期間を適用していないことを識別できる repository error として扱う。
3. Where dry run mode が指定される, the BigQuery Session Repository shall session list、detail lookup、sync write の実 data 変更を行わず、実行予定内容または検証結果を返す。
4. Where maximum bytes billed が指定される, the BigQuery Session Repository shall 指定上限を超える BigQuery 実行を成功扱いにしない。
5. If BigQuery 実行が credentials、権限、schema 不整合、費用上限、または query 失敗で完了できない, the BigQuery Session Repository shall 呼び出し側が失敗種別を識別できる repository error として返す。
6. The BigQuery Session Repository shall 高度な Search Index、semantic search、長期的な production operation policy をこの feature の完了条件に含めない。

### Requirement 6: Fake repository と検証契約

**Objective:** As a backend 開発者, I want 実 BigQuery 接続なしで repository 利用側の主要契約を検証できる, so that unit test と API 開発をローカルで安定して進められる。

#### 受け入れ基準

1. The BigQuery Session Repository shall 実 BigQuery client を使わない fake repository を提供し、session list、detail lookup、session 保存、sync run 保存の主要契約を検証できるようにする。
2. When fake repository が row を保存するとき, the BigQuery Session Repository shall 必須 field、許可された状態値、非負 count、JSON object payload、sync lifecycle の契約違反を検出できる。
3. When repository contract tests が実行される, the BigQuery Session Repository shall fake repository と BigQuery repository の一覧条件、detail lookup、not found、保存件数、degraded、sync run 状態の代表挙動を比較できる。
4. Where 実 BigQuery dataset を使う integration test が含まれる, the BigQuery Session Repository shall opt-in 条件が満たされた場合だけ実接続検証を行う。
5. If BigQuery credentials が開発者環境に存在しない, the BigQuery Session Repository shall fake repository と SQL / contract validation によって主要 unit test を継続できる。
6. When repository test case が追加または更新される, the BigQuery Session Repository shall 各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを持つ。

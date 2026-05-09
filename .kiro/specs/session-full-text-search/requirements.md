# 要件定義書

## プロジェクト記述（入力）
**課題:** GitHub Copilot CLI のローカル会話履歴を読み返す利用者は、日付範囲だけでは目的のセッションへ素早く辿り着けない。会話本文、エラー文言、ツール呼び出し、issue message などの断片を覚えていても、現状は一覧を開いて preview と詳細を順に確認する必要がある。  
**現状:** アプリは raw files を明示同期で保存済み read model に取り込み、セッション一覧・詳細は保存済み read model から返す。frontend には一覧、日付範囲フィルタ、詳細画面、会話表示、activity / issue 表示、手動同期導線があるが、日付以外の探索条件はない。  
**変更したいこと:** 利用者が一覧画面で検索語を入力し、保存済みセッションの会話本文や関連メタ情報に一致するセッションだけを確認できるようにする。検索は日付範囲と併用でき、結果が空の場合や検索条件を解除した場合も既存の read-only 閲覧体験と整合させる。

## はじめに
この仕様は、GitHub Copilot CLI のローカル会話履歴を読み返す利用者が、覚えている断片的な語句から保存済みセッションを探せるようにするための要件を定義する。

対象は、同期済みセッションを検索可能な状態に保つこと、セッション一覧取得で検索語と日付範囲を併用できること、一覧画面で検索語の入力・適用・解除・状態表示を行えることに限定する。検索は既存の read-only 閲覧体験を拡張するものであり、履歴の編集、削除、共有、自動同期、詳細画面内検索は扱わない。

## 境界コンテキスト
- **対象範囲**: 保存済みセッションの検索対象テキスト、明示同期後の検索可能状態、セッション一覧取得での検索語条件、日付範囲と検索語の併用、一覧画面の検索入力・適用・解除、検索中・検索結果・検索空状態・検索条件エラーの表示、backend / frontend tests
- **対象外**: 外部検索サービス、semantic search、ベクトル検索、検索結果スコアリング、検索語ハイライト、repository / branch / model 専用フィルタ、並び替え UI、pagination、詳細画面内検索、履歴の編集・削除・共有、自動同期、認証・認可、raw files の直接検索
- **隣接前提**: `history-db-read-model` は保存済みセッションの summary / detail payload と履歴由来メタ情報を提供する。`history-sync-api` は raw files から保存済み read model を明示更新する。`session-api-db-query` は一覧取得の保存済み read model 参照と日付範囲条件を提供する。`session-date-filtering` は frontend の日付条件管理と同期後再取得の条件維持を提供する。

## 要件

### 要件1: 保存済みセッションを検索可能な状態に保つ
**目的:** As a ローカル会話履歴を読み返す利用者, I want 同期済みセッションの本文や関連情報が検索対象になってほしい, so that 覚えている断片から目的のセッションを見つけられる

#### 受け入れ基準
1. When セッションが明示同期によって保存または更新される, the Copilot History Application shall そのセッションを一覧検索の対象として利用できる状態にする。
2. When セッションが検索対象として利用できる状態になる, the Copilot History Application shall 会話本文、会話要約、tool call の名称または引数概要、activity のタイトルまたは本文、issue の code または message、作業コンテキスト、選択モデルを検索対象に含める。
3. When current 形式または legacy 形式のセッションが検索対象になる, the Copilot History Application shall 保存形式にかかわらず同じ検索体験で扱える状態にする。
4. If セッションに degraded 状態または issue 情報が含まれる, the Copilot History Application shall 読み取れた範囲の検索対象を保持し、degraded 状態または issue 情報を検索対象から失わせない。
5. The Copilot History Application shall 検索対象の準備を保存済み read model の再生成可能な補助情報として扱い、raw files を一次ソースとする方針を変更しない。

### 要件2: セッション一覧を検索語で絞り込める
**目的:** As a 履歴から特定の会話を探す利用者, I want セッション一覧を覚えている語句で絞り込みたい, so that preview と詳細を順番に開く手間を減らせる

#### 受け入れ基準
1. When クライアントが検索語を指定してセッション一覧を要求する, the Backend Session API shall 保存済み検索対象にその検索語が一致するセッションだけを一覧対象にする。
2. When クライアントが検索語と日付範囲を指定してセッション一覧を要求する, the Backend Session API shall 検索語と日付範囲の両方に一致するセッションだけを一覧対象にする。
3. When クライアントが検索語を指定せずにセッション一覧を要求する, the Backend Session API shall 既存の日付範囲条件だけで一覧対象を決定する。
4. When セッション一覧を返す, the Backend Session API shall 既存の一覧 response shape、件数 meta、degraded 状態、issue 情報を維持する。
5. If 検索語に一致するセッションが存在しない, the Backend Session API shall 失敗応答ではなく 200 の成功応答として空の `data` と件数 0 の `meta` を返す。
6. If 検索条件が受け付けられない値として指定された, the Backend Session API shall 成功応答と区別できるクライアントエラーを返す。

### 要件3: 一覧画面で検索語を適用・解除できる
**目的:** As a 一覧画面を使う利用者, I want 検索語を入力して適用し、不要になったら解除したい, so that 日付条件と組み合わせながら探索範囲を調整できる

#### 受け入れ基準
1. When 利用者がセッション一覧画面を表示する, the Copilot History Application shall 検索語を入力できる操作を一覧条件として提供する。
2. When 利用者が検索語を入力して適用する, the Copilot History Application shall 現在の日付範囲を維持したまま検索語に一致するセッション一覧を表示する。
3. When 利用者が検索語を解除する, the Copilot History Application shall 現在の日付範囲を維持したまま検索語なしのセッション一覧を表示する。
4. While 検索語が適用されている, the Copilot History Application shall 利用者が現在の検索語と日付範囲を一覧画面上で確認できる状態を保つ。
5. When 履歴同期後に一覧が再取得される, the Copilot History Application shall 適用中の検索語と日付範囲を維持したまま結果を更新する。
6. If 利用者が別の検索語へ切り替える, the Copilot History Application shall 直前の別検索語の一覧を新しい条件の確定結果として表示し続けない。

### 要件4: 検索結果の状態を既存閲覧体験と区別して示す
**目的:** As a 検索結果を確認する利用者, I want 検索中、該当なし、入力エラー、通常の空一覧を見分けたい, so that 次に検索条件を変えるべきか同期すべきか判断できる

#### 受け入れ基準
1. While 検索条件を含む一覧取得が進行している, the Copilot History Application shall 検索条件を含む一覧を読み込んでいることを利用者が識別できる状態にする。
2. When 検索条件に一致するセッションが表示される, the Copilot History Application shall その結果が現在の検索語と日付範囲に基づくことを利用者が確認できる状態にする。
3. If 検索語を適用した状態で一致するセッションが存在しない, the Copilot History Application shall 通常の空一覧および取得失敗と区別できる検索空状態を表示する。
4. If 検索条件に対するクライアントエラーが返る, the Copilot History Application shall 一覧取得失敗と区別できる形で検索条件を修正できる状態を示す。
5. If 検索条件を含む一覧取得が失敗する, the Copilot History Application shall 履歴データを編集または削除する操作を提示せず、read-only の再試行または条件見直しに留める。

### 要件5: 全文検索の適用範囲を明確に保つ
**目的:** As a プロダクト保守者, I want 初期の全文検索が既存の read-only 一覧探索に閉じていてほしい, so that 後続のランキングや専用フィルタを別仕様として段階的に追加できる

#### 受け入れ基準
1. Where 全文検索機能が提供される, the Copilot History Application shall セッション一覧の絞り込み条件として検索語を追加する。
2. The Copilot History Application shall この feature によって検索結果スコアリング、検索語ハイライト、semantic search、ベクトル検索、外部検索サービスを必須にしない。
3. The Copilot History Application shall この feature によって repository、branch、model の専用フィルタ、並び替え UI、pagination、または詳細画面内検索を追加しない。
4. The Copilot History Application shall この feature によって履歴の編集、削除、共有、認証、認可、または自動同期の操作を追加しない。
5. The Copilot History Application shall 通常表示と検索表示のどちらでも保存済み read model を参照し、一覧検索時に raw files を直接検索しない。
6. The Copilot History Application shall 既存の read-only 閲覧体験を維持したまま検索による探索を追加する。

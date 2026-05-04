# 要件定義書

## プロジェクト記述（入力）
**課題:** GitHub Copilot CLI のローカル会話履歴を読み返す利用者は、広い期間のセッション一覧を一括で扱うと目的の会話を探しづらく、長い文字列やコードブロックが画面全体の読解性も下げている。  
**現状:** backend には日付範囲で一覧を絞り込む契約がある一方、frontend の一覧画面には日付フィルタ UI がなく、初期表示も直近 30 日を前提にしている。  
**変更したいこと:** 利用者が一覧画面で開始日・終了日を指定して対象期間のセッションだけを確認でき、初期表示は直近 7 日に絞られ、長い内容はページ全体を横スクロールさせずに読めるようにする。

## はじめに
この仕様は、GitHub Copilot CLI のローカル会話履歴を読み返す利用者が、必要な期間のセッションを素早く見つけ、一覧と詳細のどちらでも文脈を読みやすく保てるようにするための要件を定義する。  

対象は、セッション一覧の日付範囲指定、条件なし初期表示の直近 7 日化、日付条件に応じた empty / validation 表示、同期後再取得時の条件維持、長い文字列やコードブロックによる横スクロールの局所化に限定する。

## 境界コンテキスト
- **対象範囲**: セッション一覧での開始日・終了日による期間絞り込み、条件なし初期表示の直近 7 日化、絞り込み結果に応じた empty / validation 表示、同期後再取得時の現在条件の維持、一覧・詳細での横スクロール抑制
- **対象外**: 日付以外の絞り込み条件、検索、並び替え、pagination、件数制限 UI、バックグラウンド同期、自動更新、履歴の編集・削除・共有、詳細画面全体の再設計
- **隣接前提**: 既存の session list API は日付範囲を指定した一覧取得を引き続き提供し、この feature はその契約を利用する。履歴同期は一覧データを更新しうるが、日付フィルタの定義自体は変更しない。current 形式と legacy 形式の履歴は、同じ read-only 閲覧体験の中で扱われる。

## 要件

### 要件1: セッション一覧を日付範囲で絞り込める
**目的:** As a ローカル会話履歴を読み返す利用者, I want 必要な期間のセッションだけを一覧で確認したい, so that 読み返したい会話へ素早く辿り着ける

#### 受け入れ基準
1. When 利用者がセッション一覧を初めて表示する, the Copilot History Application shall 要求時点から直近 7 日間に該当するセッションだけを初期表示する。
2. When 利用者が開始日と終了日を指定して一覧を適用する, the Copilot History Application shall その両端を含む期間に該当するセッションだけを表示する。
3. When 利用者が開始日だけを指定して一覧を適用する, the Copilot History Application shall その開始日以降に該当するセッションだけを表示する。
4. When 利用者が終了日だけを指定して一覧を適用する, the Copilot History Application shall その終了日以前に該当するセッションだけを表示する。
5. When 利用者が開始日と終了日をどちらも未入力の状態で一覧を適用する, the Copilot History Application shall 初期表示と同じく要求時点から直近 7 日間に該当するセッションだけを表示する。
6. While 日付範囲が適用されている, the Copilot History Application shall 利用者が現在の開始日と終了日を一覧画面上で確認できる状態を保つ。

### 要件2: 日付条件に応じた結果状態を明確にする
**目的:** As a 一覧結果を見比べる利用者, I want いま見ている結果がどの期間のものかを誤解せず確認したい, so that 関係のないセッションを選ばずに済む

#### 受け入れ基準
1. When 利用者が日付範囲を変更して新しい一覧を表示する, the Copilot History Application shall 変更後の条件に一致するセッションだけを結果として扱う。
2. When 利用者が日付条件を適用した状態で履歴同期後に一覧を再取得する, the Copilot History Application shall 同じ日付条件を維持したまま結果を更新する。
3. If 指定した日付範囲に一致するセッションが存在しない, the Copilot History Application shall 取得失敗と区別できる絞り込み専用の空状態を表示する。
4. While 絞り込み専用の空状態が表示されている, the Copilot History Application shall 利用者が現在の開始日と終了日を確認して条件を見直せる状態を保つ。
5. If 利用者が別の日付条件へ切り替える, the Copilot History Application shall 直前の別条件の一覧を新しい条件の確定結果として表示し続けない。

### 要件3: 無効な日付範囲を一覧取得前に防ぐ
**目的:** As a 日付条件を入力する利用者, I want 無効な期間指定をすぐに修正したい, so that 誤った条件で一覧を再取得せずに済む

#### 受け入れ基準
1. If 利用者が開始日を終了日より後に指定する, the Copilot History Application shall 条件を適用せずに範囲が無効であることを示す。
2. While 開始日が終了日より後である, the Copilot History Application shall 利用者がその範囲を成功した一覧条件として送信できない状態を保つ。
3. When 利用者が無効な範囲を有効な範囲へ修正する, the Copilot History Application shall 修正後の条件で一覧を適用できるようにする。
4. If 利用者が開始日だけまたは終了日だけを指定する, the Copilot History Application shall その入力を無効範囲として扱わない。
5. The Copilot History Application shall 無効な日付範囲の理由を一覧取得前に読み取れる形で示す。

### 要件4: 長い内容の横スクロールを該当ブロック内に閉じる
**目的:** As a 一覧や詳細を読み返す利用者, I want 長い文字列やコードがあっても画面全体を横移動せずに読みたい, so that 文脈を見失わずに履歴を追える

#### 受け入れ基準
1. When セッション一覧に長いセッション ID またはメタデータが表示される, the Copilot History Application shall ページ全体に横スクロールを発生させずに一覧を読める状態を保つ。
2. When セッション詳細に長い本文、補助情報、または引数表示が含まれる, the Copilot History Application shall ページ全体に横スクロールを発生させずに主要な文脈を読める状態を保つ。
3. Where コードブロックまたは整形済みテキストが表示領域より広い, the Copilot History Application shall 必要な横方向の移動をそのブロック内だけで行えるようにする。
4. While 長い内容が折り返しまたは局所スクロールで表示されている, the Copilot History Application shall 周辺の一覧、ヘッダー、または会話文脈を同じ画面幅で読み続けられる状態を保つ。
5. If 横方向に長い内容が存在しない, the Copilot History Application shall この feature の導入によって既存の可読性を低下させない。

### 要件5: 日付フィルタの適用範囲を明確に保つ
**目的:** As a 履歴探索機能を使う利用者, I want 今回追加される操作の範囲を誤解せず使いたい, so that 期待外れの検索や編集操作を探し回らずに済む

#### 受け入れ基準
1. Where 日付フィルタ機能が提供される, the Copilot History Application shall セッション一覧の絞り込み条件として日付範囲だけを追加する。
2. The Copilot History Application shall この feature によって検索、repository、branch、model、並び替え、pagination、または件数制限の新しい操作を必須にしない。
3. The Copilot History Application shall この feature によって履歴の編集、削除、共有、または自動更新の操作を追加しない。
4. While current 形式と legacy 形式のセッションが同じ一覧に含まれる, the Copilot History Application shall 保存形式にかかわらず同じ日付絞り込み体験を提供する。
5. The Copilot History Application shall 既存の read-only 閲覧体験を維持したまま日付範囲による探索を追加する。

# 実装計画

- [x] 1. Python reader の実行前提と共有 contract を整える
- [x] 1.1 Python backend から reader package を import できる実行前提を整える
  - YAML 読取に必要な runtime dependency を backend の package 設定へ追加する
  - reader package が既存の backend quality command から import / typecheck 対象になるようにする
  - 完了時には backend の test / lint / typecheck entrypoint が reader package を解決でき、依存不足で失敗しない
  - _Requirements: 1.5, 2.2, 6.5_

- [x] 1.2 normalized session、event、issue、result、projection の共有 contract を固定する
  - source format、source state、event kind、mapping status、severity、issue code の許容値を表現する
  - root failure と session degraded issue を異なる result branch として扱えるようにする
  - event count、message snapshot count、issue count、degraded state は保持値ではなく session 内容から参照できるようにする
  - 完了時には reader と projector が同じ typed contract を使い、HTTP response、保存 schema、frontend DTO を含まない
  - _Requirements: 1.3, 1.4, 4.4, 4.5, 6.1, 6.2, 6.5_

- [x] 1.3 shared contract の基礎テストと fixture 配置を用意する
  - current、legacy、degraded、mixed root を検証できる代表 fixture を Python tests から参照できるようにする
  - contract の immutable 性、enum validation、count property、root failure union を単体テストで固定する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には fixture と contract tests だけで reader 実装前の型・境界期待を検証できる
  - _Requirements: 4.4, 4.5, 6.3, 6.4, 6.5_

- [ ] 2. 履歴 root と session source の発見境界を実装する
- [ ] 2.1 履歴 root の解決と fatal failure 分類を実装する
  - 明示 root、`COPILOT_HOME`、fallback root の優先順位で local filesystem root を解決する
  - 存在しない、directory でない、参照できない root を session issue ではなく root failure として分類する
  - file watch、外部送信、自動監視を行わない read-only 境界を守る
  - 完了時には root failure result が session 成功結果と混ざらずに返せる
  - _Requirements: 1.1, 1.4, 1.5, 6.2_
  - _Boundary: RootResolver_

- [ ] 2.2 current / legacy の session source 列挙を実装する
  - current source は session id、source format、raw file location、workspace / event artifact path を識別できる形で返す
  - legacy source は JSON file から session id fallback、source format、raw file location を識別できる形で返す
  - current と legacy が同じ root に共存しても deterministic order で同じ一覧へ含める
  - 完了時には source discovery が file content を parse せず、後続 reader が必要な metadata を受け取れる
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 3.1_
  - _Boundary: SourceCatalog_

- [ ] 2.3 root / source discovery の失敗・共存ケースをテストで固定する
  - missing root、unreadable root、non-directory root を fatal failure として検証する
  - mixed root の current / legacy source と artifact path を検証する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には root failure と source discovery の境界が regression test で守られる
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 6.2, 6.4_
  - _Boundary: RootResolver, SourceCatalog_

- [ ] 3. Raw event を normalized event へ変換する中核を実装する
- [ ] 3.1 既知 message / activity event の分類を実装する
  - current と legacy の user / assistant / system message を role、content、timestamp、raw traceability 付きで分類する
  - assistant turn、tool execution、hook、skill などの detail event を activity で追跡できる情報へ分類する
  - sequence は reader から渡された source order を保持する
  - 完了時には既知 event が event kind、role、本文、発生時刻、raw payload を持つ normalized event として返る
  - _Requirements: 2.3, 4.1, 4.4_
  - _Boundary: EventNormalizer_

- [ ] 3.2 unknown / partial event と tool call の追跡性を実装する
  - 未知 shape は unknown event として raw content を保持する
  - 属性不足や壊れた tool request は partial mapping issue として返し、読めた属性は保持する
  - tool call arguments は secret 系 key を再帰的に redact し、長い preview は truncate 状態を示す
  - 完了時には unknown / partial event でも raw payload が失われず、issue と normalized event を同時に検証できる
  - _Requirements: 2.5, 4.1, 4.2, 4.3, 6.1_
  - _Boundary: EventNormalizer_

- [ ] 3.3 event normalization の互換テストを追加する
  - known message、detail、unknown、partial、tool call redaction、tool call truncation を単体テストで検証する
  - current / legacy の代表 raw event が同じ normalized contract へ写像されることを検証する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には Rails 互換の event mapping 表に対応する主要ケースが Python tests で固定される
  - _Requirements: 4.1, 4.2, 4.3, 6.3, 6.4_
  - _Boundary: EventNormalizer_

- [ ] 4. Current / legacy format reader を実装する
- [ ] 4.1 (P) current session の workspace metadata 読取を実装する
  - workspace metadata から session id、作業ディレクトリ、repository context、created / updated timestamp を normalized session へ対応付ける
  - YAML は safe load に限定し、欠損、非 mapping、parse failure、unreadable file を session issue として扱う
  - events が存在しない場合は workspace_only state と issue で表し、session 自体は返す
  - 完了時には current workspace だけでも後続が参照できる normalized session が返る
  - _Requirements: 2.1, 2.2, 2.4, 4.4, 6.1_
  - _Boundary: CurrentReader_

- [ ] 4.2 (P) legacy session JSON 読取を実装する
  - legacy JSON から session id、開始時刻、selected model、timeline、chat message snapshot を normalized session へ対応付ける
  - 空、欠損、parse failure、unreadable file を対象 session の issue として扱い、raw traceability を保持する
  - current-only field がない場合は `None` として扱い、legacy raw payload 由来の情報を追跡可能にする
  - 完了時には legacy session が current と同じ normalized session contract で返る
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 4.4, 6.1_
  - _Boundary: LegacyReader_

- [ ] 4.3 current events JSONL の読取と selected model 判定を実装する
  - events JSONL を line order で読み、parse 可能な event を source order のまま normalizer へ渡す
  - 解釈不能な行や部分的な event は読める event を保持したまま session degraded issue にする
  - selected model は設計の優先順位と同一優先度で後勝ちの rule に従って決定する
  - 完了時には current event sequence、selected model、degraded issue が 1 つの normalized session で参照できる
  - _Requirements: 2.1, 2.3, 2.5, 4.1, 4.4, 6.1_
  - _Depends: 3.1, 3.2, 4.1_

- [ ] 4.4 current / legacy reader の単体テストを追加する
  - current metadata、event order、selected model 優先順位、workspace parse failure、JSONL parse failure、workspace_only を検証する
  - legacy field mapping、timeline normalization、message snapshot、invalid JSON、unreadable source を検証する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には current / legacy の正常系と degraded 系が reader 単位で regression test される
  - _Requirements: 2.2, 2.3, 2.4, 2.5, 3.2, 3.4, 3.5, 6.1, 6.4_
  - _Depends: 4.1, 4.2, 4.3_

- [ ] 5. Catalog reader と projection を統合する
- [ ] 5.1 root 解決から current / legacy reader 呼び出しまでの catalog reader を実装する
  - root failure 時は source 列挙や session read に進まず failure result を返す
  - current と legacy session を同じ success result の sessions としてまとめる
  - 個別 session の degraded issue を root failure へ昇格させず、他 session の読取を継続する
  - 完了時には mixed root から current / legacy の normalized session を同じ result branch で取得できる
  - _Requirements: 1.2, 1.4, 2.6, 3.3, 3.4, 6.1, 6.2_
  - _Depends: 2.1, 2.2, 4.1, 4.2, 4.3_

- [ ] 5.2 conversation projection を実装する
  - user / assistant の非空本文 message を source order の conversation entry として返す
  - assistant の tool-only event は空 conversation entry にせず、tool context を activity 側で追えるように残す
  - message count、preview、empty reason を downstream が参照できる summary として返す
  - 完了時には normalized session から conversation entry と summary を安定して生成できる
  - _Requirements: 5.1, 5.2, 5.4_
  - _Boundary: Projectors_

- [ ] 5.3 activity と search text source の projection を実装する
  - system、tool execution、hook、skill、unknown、非会話 event を conversation と区別した activity entry として返す
  - conversation content、preview、issue message を検索用テキストの基礎情報としてまとめる
  - semantic search、ranking、外部 index 更新、保存 schema 生成は含めない
  - 完了時には downstream presenter / repository が使える activity projection と search text source が reader contract から生成できる
  - _Requirements: 5.2, 5.3, 5.5, 5.6, 6.5_
  - _Boundary: Projectors_

- [ ] 5.4 catalog reader と projection の統合テストを追加する
  - mixed root で current / legacy が同じ success result に含まれることを検証する
  - root failure、session degraded、conversation、activity、search text source の代表結果を検証する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には catalog entrypoint と projections が後続 spec の入力として一括検証される
  - _Requirements: 2.6, 3.3, 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.3, 6.4_
  - _Depends: 5.1, 5.2, 5.3_

- [ ] 6. Python reader 全体の互換性と対象外責務を検証する
- [ ] 6.1 Rails / API contract fixture 由来の代表互換性を検証する
  - current / legacy の normalized session、conversation projection、activity projection、issue 表現を fixture で比較できるようにする
  - Rails 参照実装と同じ source semantics を保ちつつ、Python contract として検証する
  - 追加する各 test case の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く
  - 完了時には後続の presenter、repository、history API spec が利用する reader 入力の互換期待値が明確になる
  - _Requirements: 3.3, 4.4, 5.1, 5.3, 6.3, 6.4_
  - _Depends: 5.4_

- [ ] 6.2 対象外責務が reader package に混入していないことを検証する
  - summary / detail presenter、HTTP error envelope、BigQuery 保存、HTTP request / response handling、frontend 表示、Rails / MySQL 削除を reader 完了条件に含めないことを確認する
  - read-only local filesystem、safe YAML load、外部送信なしの境界を quality checks とテストで守る
  - 完了時には reader package の public surface が raw reader、normalized contract、projection に限定されている
  - _Requirements: 1.5, 4.5, 5.6, 6.5_
  - _Depends: 6.1_

- [ ] 6.3 backend quality gate を通して実装完了を確認する
  - Python unit tests、lint、strict typecheck を既存 backend entrypoint で実行する
  - 失敗した場合は reader contract、fixture、typing、formatting のいずれかへ原因を戻して修正する
  - 完了時には backend quality command が成功し、すべての spec 要件が tasks 上で実装済みとして追跡できる
  - _Requirements: 6.3, 6.4, 6.5_
  - _Depends: 6.2_

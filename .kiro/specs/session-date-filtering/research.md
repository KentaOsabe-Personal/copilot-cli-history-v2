# 調査メモ

## Summary
- **Feature**: `session-date-filtering`
- **Discovery Scope**: Extension
- **Key Findings**:
  - `GET /api/sessions` はすでに `from` / `to` / one-sided range / invalid query envelope を持っており、frontend から explicit query を送れば日付絞り込みを実現できる。両日付空 apply も no-query に戻さず explicit default 7-day として扱うのが安全である。
  - `useSessionIndex` は現状「client ごとに 1 つの reusable snapshot」しか持たないため、日付条件を導入するなら applied range を request 開始時点で確定し、query-keyed snapshot と分けないと別条件の一覧や error 表示を取り違える。
  - frontend の時刻表示は固定で JST だが、backend の一覧絞り込みは `updated_at_source` 優先・未設定時 `created_at_source` fallback で動く。date input は JST 境界付き ISO8601 に変換して送り、一覧カード側も同じ優先順の表示時刻を出すのがもっとも小さい変更で一貫性を保てる。

## Research Log

### 既存 session list API 契約
- **Context**: 日付フィルタ追加で backend 変更が必要かを判断するため。
- **Sources Consulted**:
  - `backend/lib/copilot_history/api/session_list_params.rb`
  - `backend/lib/copilot_history/api/session_index_query.rb`
  - `backend/spec/lib/copilot_history/api/session_list_params_spec.rb`
  - `backend/spec/requests/api/sessions_spec.rb`
- **Findings**:
  - parser は `from` / `to` を date-only または ISO8601 datetime として受け付ける。
  - 両方未指定時だけ backend 側で「直近 30 日」を既定適用する。
  - one-sided range と invalid range (`from_after_to`) は既存契約として request spec で固定済みである。
- **Implications**:
  - backend の endpoint や response shape を変えずに、frontend 側の query 送信で要件 1, 2, 3 を満たせる。
  - 30 日既定を backend で 7 日へ変える必要はなく、frontend が mount 時と両日付空 apply 時に明示 range を送る方が既存契約への影響が小さい。

### Frontend 一覧取得と同期再読込の接点
- **Context**: 日付条件適用時に stale list を見せないことと、同期後も同じ条件を保つ方法を決めるため。
- **Sources Consulted**:
  - `frontend/src/features/sessions/hooks/useSessionIndex.ts`
  - `frontend/src/features/sessions/hooks/useHistorySync.ts`
  - `frontend/src/features/sessions/pages/SessionIndexPage.tsx`
  - `frontend/src/features/sessions/hooks/useSessionIndex.test.tsx`
  - `frontend/src/features/sessions/hooks/useHistorySync.test.tsx`
- **Findings**:
  - `useSessionIndex` は mount 時 fetch と same-client reusable snapshot を持つが、query key を区別していない。
  - `reloadSessions` は same request の refresh 用に previous snapshot を残す設計であり、同一条件の同期後再取得には向く。
  - `useHistorySync` は `reloadSessions` callback だけを知り、一覧条件自体は保持していない。
- **Implications**:
  - hook 側で applied range を所有し、valid submit 時点で normalized range を current applied range として確定したうえで、`reloadSessions()` が常に latest applied range の query を再利用する必要がある。
  - 別条件の apply と同一条件の refresh を同じ挙動にすると 2.5 を破るため、`applyRange(nextRange)` と `reloadSessions()` は visible state policy を分ける設計が必要である。

### empty state の意味づけ
- **Context**: 要件 2.3 / 2.4 を満たす empty 表示が、取得失敗や「履歴が一切ない状態」と混同されないようにしたい。
- **Sources Consulted**:
  - `frontend/src/features/sessions/components/SessionEmptyState.tsx`
  - `frontend/src/features/sessions/pages/SessionIndexPage.tsx`
  - `frontend/src/features/sessions/api/sessionApi.types.ts`
  - `backend/lib/copilot_history/api/session_index_query.rb`
- **Findings**:
  - index API response には「現在の range に 0 件だった」以外の global empty 判定材料がない。
  - 現在の `SessionEmptyState` copy は「一覧そのものがまだ存在しない」意味に寄っており、default 7-day empty と filtered empty を区別しにくい。
  - `synced_empty` は sync API 実行結果に紐づく banner state であり、一覧 empty の意味づけとは別に扱える。
- **Implications**:
  - empty panel は常に current applied range を主語にした range-scoped copy を基本とし、global empty は推論しない。
  - `synced_empty` は empty panel そのものの意味を変えず、補助メッセージとして扱うのが安全である。

### 一覧カードの時刻表示と絞り込み根拠
- **Context**: user が「なぜこの session がこの期間に含まれるのか」を一覧カードから理解できるようにしたい。
- **Sources Consulted**:
  - `backend/lib/copilot_history/api/session_index_query.rb`
  - `frontend/src/features/sessions/presentation/formatters.ts`
  - `frontend/src/features/sessions/components/SessionSummaryCard.tsx`
  - `frontend/src/features/sessions/api/sessionApi.types.ts`
- **Findings**:
  - backend の一覧絞り込みと並び順は `updated_at_source` を優先し、未設定時だけ `created_at_source` を採用する。
  - 現在の一覧カード metadata は `updated_at` だけを表示し、created-only session では「時刻不明」になりうる。
  - summary payload には `created_at` と `updated_at` の両方がすでに含まれている。
- **Implications**:
  - 一覧カードは filter basis と同じ優先順 (`updated_at ?? created_at`) の表示時刻を使う helper を持つべきである。
  - これにより current / legacy 混在でも date filter の理由が一覧側で説明可能になる。

### JST 表示と date input 境界
- **Context**: 利用者は JST 表示で履歴を読むため、date filter の日境界も同じ認識で扱う必要がある。
- **Sources Consulted**:
  - `frontend/src/features/sessions/presentation/formatters.ts`
  - `frontend/src/features/sessions/presentation/formatters.test.ts`
  - `backend/config/application.rb`
  - `backend/lib/copilot_history/api/session_list_params.rb`
- **Findings**:
  - frontend の timestamp 表示は `Asia/Tokyo` 固定で `JST` suffix を付与している。
  - backend は `config.time_zone` を明示しておらず、date-only parse は server `Time.zone` に依存する。
  - parser は offset 付き ISO8601 datetime をそのまま受け入れる。
- **Implications**:
  - date input の `YYYY-MM-DD` は query 送信前に `T00:00:00+09:00` / `T23:59:59.999999+09:00` へ変換し、利用者が見ている JST 日付と API 絞り込みの境界を一致させる。
  - backend の timezone 設定変更はこの spec の責務外とし、既存 contract の使い方で一貫性を担保する。

### 横スクロールのホットスポット
- **Context**: 長い値の表示を page 全体ではなく各ブロック内に閉じる責務範囲を決めるため。
- **Sources Consulted**:
  - `frontend/src/features/sessions/components/SessionSummaryCard.tsx`
  - `frontend/src/features/sessions/components/SessionDetailHeader.tsx`
  - `frontend/src/features/sessions/components/TimelineContent.tsx`
  - `frontend/src/features/sessions/components/ActivityTimeline.tsx`
  - `frontend/src/features/sessions/components/IssueList.tsx`
  - `frontend/src/app/AppShell.tsx`
- **Findings**:
  - code / raw payload / arguments preview には `overflow-x-auto` が一部あるが、長い session id、metadata value、issue source_path、detail page 上部の session id には wrap 方針がない。
  - prose 系 block は `whitespace-pre-wrap` を使っているが、長い token を含む detail body や path は `break-words` / `break-all` が不足している。
  - shell 文言には「絞り込みを提供しない」が残っている。
- **Implications**:
  - overflow 対策は page-wide clipping ではなく、content type ごとに「prose は wrap」「id/path/meta は token break」「pre/code は local scroll」で整理する。
  - `AppShell` の product copy も新 scope に合わせて更新する必要がある。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Frontend-owned explicit date range | frontend が default 7-day / validation / query serialization を持ち、既存 `/api/sessions` に `from` / `to` を送る | backend 変更が最小、sync reload と UI state を feature 内に閉じやすい | query key を誤ると stale list を見せる | **採用** |
| Backend default を 7 日へ変更 | no-query 既定を backend で 7 日に変更し、frontend は date UI だけ追加する | 初期表示だけなら変更点が少ない | 他 caller の既定範囲も変わる、user-selected range と sync retention は別途 frontend 管理が必要 | default 変更だけでは要件 2, 3 を満たさない |
| URL query / global store に filter を永続化 | route query または外部 state に日付条件を保存する | deep link や refresh persistence に拡張しやすい | 仕様外の永続化と複雑さを持ち込む | 今回は過剰 |

## Design Decisions

### Decision: frontend が applied range を所有し、backend には explicit query を送る
- **Context**: 初期 7 日表示と user-selected range を既存 API 契約で実現したい。
- **Alternatives Considered**:
  1. backend の既定範囲を 7 日へ変更する
  2. frontend が mount / apply 時に毎回 explicit query を送る
- **Selected Approach**: frontend に `SessionDateRangeDraft` と `SessionIndexQuery` 変換 helper を持たせ、mount 時と apply 時に `from` / `to` を明示送信する。両日付空 apply は helper が default 7-day range へ解決して no-query に戻さない。
- **Rationale**: 既存 request / parser contract を再利用でき、他 caller の backend default 30 日を壊さず、空入力時の意味も frontend で一貫して固定できる。
- **Trade-offs**: query serialization と cache key 管理は frontend 側で増えるが、責務は `features/sessions` に閉じる。
- **Follow-up**: initial mount と one-sided range の fetch URL を test で固定する。

### Decision: `useSessionIndex` は query-keyed snapshot を持ち、same-range reload と new-range apply を分ける
- **Context**: 同期後再取得では current filter を保ちたい一方、別条件適用時に古い一覧を新条件の確定結果として見せてはいけない。
- **Alternatives Considered**:
  1. 既存どおり client 単位の単一 snapshot を使う
  2. applied query key 付き snapshot と request policy を持つ
- **Selected Approach**: hook は applied range を state と ref の両方で保持し、valid submit 時点で normalized range を current applied range として確定する。`reloadSessions()` は latest applied range ref を読む same-range refresh として previous snapshot を維持し、`applyRange()` は new-range loading として previous different-range snapshot を visible success に使わない。
- **Rationale**: 要件 2.2 と 2.5 を同時に満たせる最小構成である。
- **Trade-offs**: hook interface と内部 state は少し広がるが、loading / error / empty のラベル根拠が `appliedRange` に一本化され、`useHistorySync` には `reloadSessions` を渡すだけで済む。
- **Follow-up**: stale request の abort、cache key mismatch、sync 中の別条件 apply 後も latest range refresh になることに加え、新条件の error でも attempted range が UI に残ることを test で固定する。

### Decision: empty state は range-scoped copy を基本とする
- **Context**: API response shape を変えずに 2.3 / 2.4 を満たしたい。
- **Alternatives Considered**:
  1. empty panel の copy で global empty と filtered empty を推論する
  2. empty panel は current applied range の 0 件だけを表し、sync outcome は banner で補足する
- **Selected Approach**: empty panel は current applied range と range label を前提にした文言だけを担い、「履歴そのものが存在しない」とは言わない。`synced_empty` は sync 完了 banner の補助文言として扱う。
- **Rationale**: `SessionIndexResponse` の `count=0` だけで説明できる範囲に責務を閉じ、error や global empty との混同を避けられる。
- **Trade-offs**: 初回 empty の copy はやや控えめになるが、誤案内を防げる。
- **Follow-up**: default 7-day empty、user-selected filtered empty、`synced_empty` banner の 3 パターンを page / component test で固定する。

### Decision: 一覧表示時刻は backend の filter basis と同じ優先順にそろえる
- **Context**: current / legacy 混在時にも一覧カード上で filter 理由を説明したい。
- **Alternatives Considered**:
  1. 現状どおり `updated_at` のみ表示する
  2. `updated_at ?? created_at` を一覧表示時刻として使う
- **Selected Approach**: `SessionSummaryCard` は `formatters` の helper を通じて `updated_at ?? created_at` を一覧表示時刻として表示し、backend `SessionIndexQuery` の candidate 選択順と合わせる。
- **Rationale**: API shape 追加なしで 1.6 / 5.4 を支え、created-only session でも「なぜこの一覧に出たか」を UI 上で示せる。
- **Trade-offs**: header/detail の表示文言と一覧カードの timestamp label が分かれる可能性はあるが、一覧探索体験の一貫性を優先する。
- **Follow-up**: created-only session が「時刻不明」ではなく filter basis timestamp を表示する test を追加する。

### Decision: 日付入力は native date input + inline validation を採用する
- **Context**: 追加 scope は date range だけであり、入力エラーは一覧取得前に読める必要がある。
- **Alternatives Considered**:
  1. 外部 date picker / form library を導入する
  2. browser 標準 `input type="date"` と typed helper で実装する
- **Selected Approach**: `SessionDateFilterForm` が draft state を受け取り、`from > to` のとき message を表示し Apply を disabled にする。
- **Rationale**: 依存追加なしで要件 3.1-3.5 を満たせ、feature の read-only UI 境界を広げない。
- **Trade-offs**: browser native UI の見た目差はあるが、今回の要件は日付入力の存在と validation で十分である。
- **Follow-up**: invalid range, one-sided valid, valid-after-fix の component test を追加する。

### Decision: overflow policy は content type ごとに分ける
- **Context**: 長い値を page 全体の横スクロールへ逃がさず、必要時だけ block 内で横移動させたい。
- **Alternatives Considered**:
  1. shell 全体に overflow hidden を強く掛ける
  2. prose / id-path-meta / pre-code の 3 種類で wrap policy を分ける
- **Selected Approach**: prose は `whitespace-pre-wrap` + `break-words`、id/path/meta は `min-w-0` + `break-all`、pre/code/raw/arguments は `overflow-x-auto` の局所 scroll に統一する。
- **Rationale**: データを隠さず requirement 4.1-4.5 を満たせる。
- **Trade-offs**: 複数 component に class 調整が分散するが、新 abstraction を増やすほどではない。
- **Follow-up**: summary/detail/issue/raw block で長い文字列を渡す rendering test を追加する。

## Risks & Mitigations
- JST 境界と backend parse がずれて別日扱いになるリスク — date input は offset 付き JST ISO8601 へ変換して送る。
- 両日付クリアを backend の no-query fallback に任せると 30 日表示へ戻るリスク — frontend helper が explicit default 7-day range へ正規化する。
- 別条件の一覧を cache から誤再利用するリスク — reusable snapshot は client だけでなく query key を含めて管理する。
- 長い unbroken token が想定外 component からはみ出すリスク — `SessionSummaryCard`, `SessionDetailHeader`, `IssueList`, `TimelineContent`, `ActivityTimeline`, `SessionDetailPage` を明示 scope に含める。
- sync 後 refresh が stale range や default 7 日へ戻るリスク — `reloadSessions()` は latest applied range ref を参照し、`useHistorySync` 側では filter state を持たない。
- empty copy が「履歴が一切ない」と誤読されるリスク — empty panel は range-scoped copy に限定し、sync outcome は banner へ分離する。
- created-only session が filter 結果の理由を説明できないリスク — 一覧表示時刻は `updated_at ?? created_at` を採用し、backend candidate 順と合わせる。

## References
- `backend/lib/copilot_history/api/session_list_params.rb` — 既存 `from` / `to` / invalid query parser
- `backend/spec/lib/copilot_history/api/session_list_params_spec.rb` — date-only / ISO8601 / one-sided / default 30 days の契約
- `frontend/src/features/sessions/hooks/useSessionIndex.ts` — 現在の reusable snapshot と reload 挙動
- `frontend/src/features/sessions/hooks/useHistorySync.ts` — sync 後 refresh の接点
- `frontend/src/features/sessions/presentation/formatters.ts` — JST 表示の既存前提
- `frontend/src/features/sessions/components/SessionSummaryCard.tsx` — 長い session id / metadata の overflow hotspot
- `frontend/src/features/sessions/components/TimelineContent.tsx` — pre/code/arguments block の overflow hotspot

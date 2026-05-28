# Research & Design Decisions

## Summary
- **Feature**: `cwd-session-tabs`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 既存の `SessionSummary` は `work_context.cwd` を保持しており、一覧成功状態の `state.sessions` から frontend 内でタブを構築できる。
  - `useSessionIndex` は日付範囲・検索語・同期後 refresh を既存 criteria として管理しているため、タブ選択は API criteria に含めず page-local state として扱う。
  - タブの主ラベルは absolute path ではなく `cwd` の最後のディレクトリ名を表示し、完全 path は補助情報として提供する必要がある。

## Research Log

### 既存 frontend 一覧境界
- **Context**: 作業ディレクトリ別タブをどの層が持つべきか確認した。
- **Sources Consulted**:
  - `frontend/src/features/sessions/pages/SessionIndexPage.tsx`
  - `frontend/src/features/sessions/hooks/useSessionIndex.ts`
  - `frontend/src/features/sessions/api/sessionApi.types.ts`
- **Findings**:
  - `useSessionIndex` は API query の日付範囲と検索語、reusable snapshot、同期後 reload を扱う。
  - 一覧成功状態は `state.status === 'success'` のときだけ `SessionSummary[]` を持ち、loading / empty / error では一覧 data が存在しない。
  - `SessionIndexQuery` は `from` / `to` / `search` のみで、cwd 専用 query param はない。
- **Implications**:
  - cwd タブは API query criteria ではなく、成功状態の `SessionSummary[]` に対する presentation state として設計する。
  - タブ切替は `fetchSessionIndex` を呼ばず、`SessionList` に渡す配列だけを変更する。
  - loading / empty / error ではタブを描画しない。

### cwd 表示と正規化の既存契約
- **Context**: `cwd` の trimming、欠損値、長い path の扱いを既存 UI と揃える必要があった。
- **Sources Consulted**:
  - `frontend/src/features/sessions/presentation/formatters.ts`
  - `frontend/src/features/sessions/components/SessionSummaryCard.tsx`
  - `frontend/tests/features/sessions/components/SessionSummaryCard.test.tsx`
- **Findings**:
  - metadata helper は `cwd?.trim()` により空白値を除外し、summary surface では `実行ディレクトリ` を表示する。
  - summary card は metadata value に `break-words` を使い、長い path がページ幅を広げないようにしている。
  - `cwd` 欠損時は placeholder を出さない既存方針がある。
- **Implications**:
  - タブ utility も `trim()` 後の値を canonical cwd とし、`null` / 空白は `ディレクトリ未設定` にまとめる。
  - タブの主ラベルは normalized cwd の basename にし、完全 path は `title` と `aria-label` で提供する。
  - 未設定タブは通常 cwd と別の `unset` key を持たせる。

### 検索・日付・同期との統合
- **Context**: 条件変更や履歴同期後に選択中タブが存在しなくなるケースを確認した。
- **Sources Consulted**:
  - `.kiro/specs/session-date-filtering/design.md`
  - `.kiro/specs/session-full-text-search/design.md`
  - `frontend/src/features/sessions/pages/SessionIndexPage.tsx`
- **Findings**:
  - 日付範囲と検索語は applied criteria として `useSessionIndex` が保持し、新しい成功結果で `state.sessions` が置き換わる。
  - 同期後 refresh は `reloadSessions()` によって現在の criteria を維持して再取得する。
  - 検索 UI の補助文は現在「実行ディレクトリの内容を検索」と案内しており、本 feature の境界では cwd を一覧タブで切り替える文脈へ更新する必要がある。
- **Implications**:
  - `SessionIndexPage` は成功結果ごとにタブ一覧を再導出し、選択 key が消えたら `all` に補正する。
  - 検索結果中の cwd タブは検索済み集合だけから作る。
  - 検索フォーム説明は cwd 検索案内から、検索結果を一覧タブで作業ディレクトリ別に切り替えられる案内へ変更する。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Frontend local tab projection | 取得済み `SessionSummary[]` から tab model と filtered sessions を導出する | API 変更なし、追加 fetch なし、検索・日付・同期の既存 criteria を維持しやすい | tab state 補正を page で明示する必要がある | 採用 |
| `useSessionIndex` に cwd tab state を統合 | hook が API criteria と tab selection をまとめて返す | page の状態は少なくなる | API criteria と presentation-only selection が混ざり、追加 fetch 不要の境界が曖昧になる | 不採用 |
| backend aggregation endpoint | server が cwd summary を返す | 大規模 pagination 時に発展しやすい | 要件外の endpoint / aggregation / response shape 変更になる | 不採用 |
| URL query に tab を永続化 | selected cwd を URL で共有可能にする | reload 復元に強い | URL persistence は既存 date/search 設計の範囲外で、path encode 方針も増える | 不採用 |

## Design Decisions

### Decision: タブは frontend local projection として構築する
- **Context**: 要件は「現在取得済みのセッション集合」を作業ディレクトリ別に切り替えることであり、API や DB 契約の変更は明示的に境界外である。
- **Alternatives Considered**:
  1. `GET /api/sessions` に cwd filter / summary を追加する。
  2. `useSessionIndex` の criteria に cwd を追加する。
  3. 成功状態の `SessionSummary[]` から frontend utility で tab model を導出する。
- **Selected Approach**: `sessionDirectoryTabs.ts` が tabs と selected sessions を導出し、`SessionIndexPage` が selected tab key を保持する。
- **Rationale**: 追加 fetch を発生させず、日付範囲・検索語・同期の既存契約を維持できる。
- **Trade-offs**: pagination が将来入る場合、取得済み page だけのタブになるため再検証が必要になる。
- **Follow-up**: 実装時は tab 切替操作が `fetchSessionIndex` を呼ばないことを page test で固定する。

### Decision: 正規化済み cwd と未設定状態を別 key にする
- **Context**: `null`、空白、長い path、同一 basename を同じ UI に押し込むと識別性が落ちる。
- **Alternatives Considered**:
  1. basename だけを key と label にする。
  2. full path をそのまま tab label と key にする。
  3. `all` / `cwd:<normalized>` / `unset` の内部 key と、basename の表示 label + 完全 path の補助情報に分ける。
- **Selected Approach**: 内部 key は normalized cwd を保持し、表示は basename と必要な親 path context を使う。未設定は `unset` に固定する。
- **Rationale**: 同一 basename を区別しつつ、長い path がタブ UI を壊さない。
- **Trade-offs**: visible label だけで full path 全体は見えないため、`title` と `aria-label` で完全 path を提供する。
- **Follow-up**: 同一 basename、空白 cwd、未設定 cwd の unit test を追加する。

### Decision: ARIA tabs pattern を軽量実装する
- **Context**: 左右キー操作、選択状態の支援技術伝達、件数を含むアクセシビリティ名が要件に含まれる。
- **Alternatives Considered**:
  1. 通常の button group として実装する。
  2. 外部 tabs library を追加する。
  3. `role="tablist"` / `role="tab"` / `aria-selected` と roving focus を既存 React state で実装する。
- **Selected Approach**: 新規依存を追加せず、`SessionDirectoryTabs` が keyboard selection と focus を扱う。
- **Rationale**: 要件に必要な操作だけを満たし、既存 stack と軽量 SPA 方針を維持できる。
- **Trade-offs**: Home / End などの高度操作は要件外にする。将来必要なら同 component 内で拡張する。
- **Follow-up**: 左右キーで隣接タブへ選択移動する component test を追加する。

## Risks & Mitigations
- 選択中 cwd が新しい成功結果から消える — `SessionIndexPage` で tabs 再導出後に `all` へ補正する。
- 長い path や多数タブでページ全体が横スクロールする — タブ列 container のみ `overflow-x-auto` とし、button label は max width + truncate にする。
- 同一 basename の tab が見分けにくい — duplicate basename の場合は親 path context を visible sublabel または label suffix として表示する。
- タブ切替が API 再取得を起こす退行 — page test で `fetchSessionIndex` / `applySearch` / `applyRange` が呼ばれないことを固定する。

## References
- `.kiro/steering/product.md` — read-only local history viewer の product boundary。
- `.kiro/steering/tech.md` — React 19 / TypeScript 6 / Tailwind CSS 4、DB read model と API 契約の維持。
- `.kiro/steering/structure.md` — frontend sessions feature slice と tests 配置。
- `.kiro/specs/session-full-text-search/design.md` — 検索 criteria と frontend state の既存境界。
- `.kiro/specs/session-execution-directory-search/design.md` — `work_context.cwd` 表示・検索互換性の既存契約。

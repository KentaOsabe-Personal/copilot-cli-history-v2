# API 契約 fixture note

## 目的

この contract note は、Rails / MySQL から Django / BigQuery へ移行するときに維持する API contract fixture set の読み方を固定する。fixture は後続の Django presenter / API / parity validation が参照する read-only expectation であり、移行先実装の都合で直接変更しない。

## 正本

fixture の正本は次の現行 artifact とする。

| 分類 | 正本 | 用途 |
|---|---|---|
| HTTP status / representative request | `backend/spec/requests/api/sessions_spec.rb`, `backend/spec/requests/api/history_syncs_spec.rb` | endpoint、query、status、error code の根拠 |
| success payload | `backend/lib/copilot_history/api/presenters/session_index_presenter.rb`, `session_detail_presenter.rb`, `history_sync_presenter.rb` | response body の `data` / `meta` shape の根拠 |
| error envelope | `backend/lib/copilot_history/api/presenters/error_presenter.rb`, `history_sync_presenter.rb` | `error.code`, `error.message`, `error.details` と failure `meta` の根拠 |
| frontend dependency | `frontend/src/features/sessions/api/sessionApi.types.ts`, `sessionApi.ts` | DTO field、raw opt-in、404 normalization の根拠 |

現行 API と frontend 型の間に命名、nullable、field presence の差分が見つかった場合は、この note の「差分 note」に記録し、fixture の期待値がどちらの正本に基づくかを明示する。

## 対象 endpoint inventory

| Scenario ID | Method | Endpoint | Request fixture | Response fixture | Status | Payload |
|---|---|---|---|---|---:|---|
| `sessions.index.list_success` | GET | `/api/sessions` | `sessions/index/list_success.request.json` | `sessions/index/list_success.response.json` | 200 | `data` 配列と `meta` object |
| `sessions.index.list_empty` | GET | `/api/sessions` | `sessions/index/list_empty.request.json` | `sessions/index/list_empty.response.json` | 200 | `data: []`, `meta.count: 0`, `meta.partial_results: false` |
| `sessions.index.list_search_empty` | GET | `/api/sessions` | `sessions/index/list_search.request.json` | `sessions/index/list_search_empty.response.json` | 200 | search / date range の該当なし成功 |
| `sessions.index.list_degraded` | GET | `/api/sessions` | `sessions/index/list_success.request.json` | `sessions/index/list_degraded.response.json` | 200 | session-level `issues`, `degraded: true`, `meta.partial_results: true` |
| `sessions.index.invalid_date_range` | GET | `/api/sessions` | `sessions/index/list_invalid_date_range.request.json` | `sessions/index/list_invalid_date_range.response.json` | 400 | `invalid_session_list_query` error envelope |
| `sessions.index.invalid_datetime` | GET | `/api/sessions` | `sessions/index/list_invalid_datetime.request.json` | `sessions/index/list_invalid_datetime.response.json` | 400 | `invalid_session_list_query` error envelope |
| `sessions.index.invalid_limit` | GET | `/api/sessions` | `sessions/index/list_invalid_limit.request.json` | `sessions/index/list_invalid_limit.response.json` | 400 | `invalid_session_list_query` error envelope |
| `sessions.index.invalid_search_control_character` | GET | `/api/sessions` | `sessions/index/list_invalid_search.request.json` | `sessions/index/list_invalid_search.response.json` | 400 | `invalid_session_list_query` error envelope |
| `sessions.index.overlong_search` | GET | `/api/sessions` | `sessions/index/list_overlong_search.request.json` | `sessions/index/list_overlong_search.response.json` | 400 | `invalid_session_list_query` error envelope |
| `sessions.show.detail_success` | GET | `/api/sessions/:id` | `sessions/show/detail_success.request.json` | `sessions/show/detail_success.response.json` | 200 | detail `data` object、conversation、activity、timeline |
| `sessions.show.detail_without_raw` | GET | `/api/sessions/:id` | `sessions/show/detail_success.request.json` | `sessions/show/detail_without_raw.response.json` | 200 | raw 未要求時の `raw_included: false` と `raw_payload: null` |
| `sessions.show.detail_with_raw` | GET | `/api/sessions/:id?include_raw=true` | `sessions/show/detail_with_raw.request.json` | `sessions/show/detail_with_raw.response.json` | 200 | `raw_included: true` と raw payload fields |
| `sessions.show.not_found` | GET | `/api/sessions/:id` | `sessions/show/detail_not_found.request.json` | `sessions/show/detail_not_found.response.json` | 404 | `session_not_found` error envelope |
| `history_sync.success` | POST | `/api/history/sync` | `history_sync/sync_success.request.json` | `history_sync/sync_success.response.json` | 200 | `data.sync_run`, `data.counts` |
| `history_sync.completed_with_issues` | POST | `/api/history/sync` | `history_sync/sync_success.request.json` | `history_sync/sync_completed_with_issues.response.json` | 200 | `completed_with_issues`, `degraded_count` |
| `history_sync.conflict` | POST | `/api/history/sync` | `history_sync/sync_success.request.json` | `history_sync/sync_conflict.response.json` | 409 | `history_sync_running` error envelope |
| `history_sync.root_failure` | POST | `/api/history/sync` | `history_sync/sync_success.request.json` | `history_sync/sync_root_failure.response.json` | 503 | root failure code と sync run `meta` |
| `history_sync.persistence_failure` | POST | `/api/history/sync` | `history_sync/sync_success.request.json` | `history_sync/sync_persistence_failure.response.json` | 500 | `history_sync_failed` error envelope と sync run `meta` |

## Status / error code matrix

| Status | Error code | Scenario | Frontend normalization | Details contract |
|---:|---|---|---|---|
| 200 | なし | list / detail / sync success | `success` | success response は top-level `data` を持ち、list は `meta` も持つ |
| 400 | `invalid_session_list_query` | invalid date range / datetime / limit / search | `backend` | `details.field`, `details.reason`, 必要に応じて `details.value` |
| 404 | `session_not_found` | missing session detail | `not_found` | `details.session_id` |
| 409 | `history_sync_running` | concurrent sync | `backend` | `details.sync_run_id`, `details.started_at` |
| 500 | `history_sync_failed` | persistence failure after run creation | `backend` | `details.failure_class`, `details.sync_run_id`, sync run `meta` |
| 503 | root failure code 例: `root_missing` | history root cannot be read | `backend` | `details.path`, sync run `meta` |

frontend は `sessionApi.ts` の `normalizeHttpError` により、404 かつ `session_not_found` の場合だけ dedicated not-found state として扱う。それ以外の backend error は `kind: "backend"` として扱えるだけの HTTP status と `error.code` を fixture に残す。

## 対象外

この spec は次を扱わない。

| 対象外 | 理由 |
|---|---|
| API shape 変更 | fixture は現行 contract の固定であり、変更判断は後続 spec または人間レビューに委ねる |
| 新規 UI 機能 | frontend が現状依存する DTO と error normalization の維持だけを扱う |
| Django backend 実装 | 後続 spec が fixture を期待値として参照する |
| BigQuery 分析 schema | API contract ではなく read model / repository 側の責務 |
| Python reader 移植 | raw files 読取仕様は隣接 spec の責務 |
| Rails / MySQL stack 削除 | 削除は migration 後の独立 spec で扱う |

## Frontend 型対応

| Fixture / field | Frontend 型 | Coverage |
|---|---|---|
| `sessions.index.*.response.body.data[]` | `SessionSummary` | `id`, `source_format`, `created_at`, `updated_at`, `selected_model`, `source_state`, counts, `degraded`, `issues` を list success / degraded で検証する |
| `work_context` | `WorkContext` | 実値と nullable 値を list success の current / legacy 例で検証する |
| `conversation_summary` | `SessionConversationSummary` | `has_conversation`, `message_count`, `preview`, `activity_count` を list success / degraded で検証する |
| `sessions.index.*.response.body.meta` | `SessionIndexMeta`, `SessionIndexResponse` | `count` と `partial_results` を success / empty / search empty / degraded で検証する |
| `sessions.show.*.response.body.data` | `SessionDetail`, `SessionDetailResponse` | detail success / raw fixtures で top-level detail fields を検証する |
| `message_snapshots[]` | `SessionMessageSnapshot` | raw 未要求時は `raw_payload: null`、raw opt-in 時は raw object を検証する |
| `conversation` | `SessionConversation`, `SessionConversationEntry` | `entries`, `message_count`, `empty_reason`, `summary`, entry-level tool calls / issues を detail success で検証する |
| `activity.entries[]` | `SessionActivity`, `SessionActivityEntry` | sequence、category、mapping status、source path、raw availability、raw payload 境界を detail fixtures で検証する |
| `timeline[]` | `SessionTimelineEvent`, `SessionTimelineToolCall`, `SessionTimelineDetail` | kind、mapping status、occurred_at、role/content、tool calls、detail、raw payload、degraded、issues を detail fixtures で検証する |
| `history_sync.*.response.body.data` | `HistorySyncResponse`, `HistorySyncRun`, `HistorySyncCounts` | `sync_run` と counts を success / completed_with_issues で検証する |
| error response `body.error` | `ErrorEnvelope`, `SessionApiError` | 400 / 404 / 409 / 500 / 503 で common envelope と frontend normalization の入力を検証する |

## Field coverage note

| Frontend field | Fixture coverage | 判定 |
|---|---|---|
| `SessionIndexQuery.from`, `to`, `search` | list success / empty / search / validation request fixtures | request fixture で検証 |
| frontend-only `SessionIndexRequest.signal` | fixture なし | HTTP contract ではなく fetch cancellation 用なので対象外 |
| `SessionApiEnvironment`, config / network error variants | fixture なし | frontend client-local error であり backend API contract 対象外 |
| `SessionConversationEmptyReason` の `no_events`, `no_conversation_messages`, `events_unavailable` | 代表 fixture では `null` のみ | 代表 fixture には含めない。empty conversation の詳細網羅は後続の presenter / parity validation で追加候補 |
| `SessionTimelineDetail` の non-null detail | 代表 detail fixture では `null` | tool call / message 中心の代表 fixtureでは対象外。detail event を契約化する場合は新 scenario 追加候補 |
| `SessionTimelineMappingStatus` / tool call status の `partial` | 代表 fixture では `complete` 中心 | degraded fixture の issue と合わせ、partial mapping の網羅は追加 fixture 候補 |
| sync completed issue details | sync response には issue list なし | 現行 `HistorySyncPresenter` と `HistorySyncResponse` は counts のみを返す。保存された issue 情報は degraded session の list/detail fixture で参照する |

## Requirement coverage

fixture scenario は payload shape と status の代表契約を担い、contract note は境界、差分、型 coverage、更新手順、downstream 利用規約を担う。全 requirement ID は次の artifact で追跡する。

| Requirement ID | Coverage artifact | 判定 |
|---|---|---|
| 1.1, 1.2 | `fixtures/manifest.json`, endpoint inventory | 対象 endpoint、request、status、payload 種別を scenario ごとに検証する |
| 1.3 | 対象外 | API shape 変更、新規 UI、Django backend、BigQuery schema、Python reader、Rails/MySQL 削除を対象外として固定する |
| 1.4 | 差分 note | raw payload、legacy work context、sync issue details、validation details の差分と期待値の根拠を固定する |
| 2.1, 2.2, 2.3, 2.4, 2.5 | `sessions/index/*.json`, endpoint inventory | list success、empty、search empty、degraded、validation request の代表契約を検証する |
| 3.1, 3.2, 3.3, 3.4, 3.5 | `sessions/show/*.json`, frontend 型対応, 差分 note | detail、conversation、activity、timeline、raw opt-in / raw 未要求境界を検証する |
| 4.1, 4.2, 4.3, 4.4, 4.5 | `history_sync/*.json`, status / error code matrix, 差分 note | sync success、completed_with_issues、conflict、root failure、persistence failure を検証する |
| 5.1, 5.2, 5.3, 5.4, 5.5 | error fixture, status / error code matrix | common error envelope、404 normalization、invalid query details、backend error 分類を検証する |
| 6.1, 6.2, 6.3, 6.4 | `fixtures/manifest.json`, frontend 型対応 | list、detail、sync、error fixture と frontend DTO の対応を検証する |
| 6.5 | Field coverage note | 代表 fixture に含めない frontend field を対象外、別 fixture、追加候補に分類する |
| 7.1 | 正本 | fixture 正本を Rails request specs / presenters と frontend 型として固定する |
| 7.2 | 更新手順 | 更新理由、endpoint、scenario、frontend 型、status / error code 変更有無の記録手順を固定する |
| 7.3 | 更新手順 | request / response shape、status、error code 変更を仕様変更候補として分類する |
| 7.4 | 目的, Manifest 規約 | 後続 Django presenter / API / parity validation が同じ fixture を read-only expectation として参照する前提を固定する |
| 7.5 | テストコメント規約, `backend/spec/contracts/api_contract_fixtures_spec.rb` | 各 `it` の直前に `概要・目的`、`テストケース`、`期待値` コメントを置く規約を検証可能な形で残す |

## Fixture 規約

request fixture は次の shape に揃える。

```json
{
  "method": "GET",
  "path": "/api/sessions",
  "query": {},
  "body": null
}
```

response fixture は次の shape に揃える。

```json
{
  "status": 200,
  "body": {
    "data": [],
    "meta": {
      "count": 0,
      "partial_results": false
    }
  }
}
```

error response は必ず common error envelope を使う。

```json
{
  "status": 404,
  "body": {
    "error": {
      "code": "session_not_found",
      "message": "session was not found",
      "details": {
        "session_id": "session-missing"
      }
    }
  }
}
```

## Manifest 規約

`fixtures/manifest.json` は fixture set の機械可読 index として扱う。各 scenario は次を持つ。

| Field | 意味 |
|---|---|
| `id` | endpoint と scenario を表す安定 ID |
| `method` / `endpoint` | 対象 HTTP contract |
| `status` | 期待 HTTP status |
| `payload_kind` | `success` または `error` |
| `request` / `response` | `fixtures/` からの相対 path |
| `requirements` | `requirements.md` の numeric ID |
| `frontend_types` | 対応する `sessionApi.types.ts` の型名 |

manifest は後続 Django presenter / API / parity validation が期待 fixture を discovery する入口である。request / response shape、status code、error code の変更が必要になった場合は manifest の差分を仕様変更候補としてレビューする。

## 更新手順

fixture を再生成または手動更新するときは、変更 PR または spec note に次を記録する。

| 記録項目 | 必須内容 |
|---|---|
| 更新理由 | Rails request spec / presenter / frontend 型のどの変更を受けたか |
| 対象 endpoint | 影響する method と path |
| 対象 scenario | manifest の scenario ID |
| 影響 frontend 型 | `SessionIndexResponse` などの型名 |
| status code 変更 | あり / なし。ありの場合は仕様変更候補として明示 |
| error code 変更 | あり / なし。ありの場合は仕様変更候補として明示 |
| request / response shape 変更 | あり / なし。ありの場合は downstream parity failure と区別する根拠を記録 |

request shape、response shape、status code、error code が変わる更新は、単なる fixture 修正ではなく仕様変更候補として扱う。後続 Django / parity validation が fixture と合わない場合も、まず移植バグか仕様変更候補かをこの手順で切り分ける。

## テストコメント規約

この spec に関する backend / frontend test を追加または更新するときは、各 `it` / test case の直前に次のコメントを残す。

- `概要・目的`
- `テストケース`
- `期待値`

この規約は `.kiro/steering/` と `AGENTS.md` の project rule に従う。

## 差分 note

| 差分 | 期待値の根拠 | 判断 |
|---|---|---|
| raw 未要求時の raw payload field | `SessionDetailPresenter` は field を消さず `raw_payload: nil` を返し、frontend 型は `unknown` を許容する | fixture は `raw_payload: null` と `raw_included: false` を期待値にする |
| legacy session の work context | frontend 型は `WorkContext` の各 field を nullable としている | list success は legacy 例で `cwd`, `git_root`, `repository`, `branch` の `null` を示す |
| sync completed issue details | 要件文は保存 issue 情報に触れるが、現行 `HistorySyncPresenter` / `HistorySyncResponse` は issue list を返さない | sync fixture は `degraded_count` を期待値にし、保存 issue 情報は degraded session fixture で検証する |
| validation error details | request spec / presenter は field、reason、必要に応じて value を返す | invalid query fixtures は `details.field`, `details.reason`, `details.value` の代表を示す |

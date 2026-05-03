export interface WorkContext {
  cwd: string | null
  git_root: string | null
  repository: string | null
  branch: string | null
}

export interface SessionIssue {
  code: string
  severity: string
  message: string
  source_path: string | null
  scope: string
  event_sequence: number | null
}

export type SessionSourceState = 'complete' | 'workspace_only' | 'degraded'

export interface SessionConversationSummary {
  has_conversation: boolean
  message_count: number
  preview: string | null
  activity_count: number
}

export interface SessionSummary {
  id: string
  source_format: string
  created_at: string | null
  updated_at: string | null
  work_context: WorkContext
  selected_model: string | null
  source_state: SessionSourceState
  event_count: number
  message_snapshot_count: number
  conversation_summary: SessionConversationSummary
  degraded: boolean
  issues: readonly SessionIssue[]
}

export interface SessionIndexMeta {
  count: number
  partial_results: boolean
}

export interface SessionIndexResponse {
  data: readonly SessionSummary[]
  meta: SessionIndexMeta
}

export interface SessionIndexQuery {
  from?: string
  to?: string
}

export interface SessionIndexRequest {
  signal?: AbortSignal
  query?: SessionIndexQuery
}

export interface SessionMessageSnapshot {
  role: string | null
  content: string | null
  raw_payload: unknown
}

export type SessionTimelineKind = 'message' | 'detail' | 'unknown'

export type SessionTimelineMappingStatus = 'complete' | 'partial'

export type SessionToolCallStatus = 'complete' | 'partial'

export interface SessionTimelineToolCall {
  name: string | null
  arguments_preview: string | null
  is_truncated: boolean
  status: SessionToolCallStatus
}

export interface SessionTimelineDetail {
  category: string
  title: string
  body: string | null
}

export interface SessionTimelineEvent {
  sequence: number
  kind: SessionTimelineKind
  mapping_status: SessionTimelineMappingStatus
  raw_type: string | null
  occurred_at: string | null
  role: string | null
  content: string | null
  tool_calls: readonly SessionTimelineToolCall[]
  detail: SessionTimelineDetail | null
  raw_payload: unknown
  degraded: boolean
  issues: readonly SessionIssue[]
}

export type SessionConversationEmptyReason =
  | 'no_events'
  | 'no_conversation_messages'
  | 'events_unavailable'
  | null

export interface SessionConversationEntry {
  sequence: number
  role: 'user' | 'assistant'
  content: string
  occurred_at: string | null
  tool_calls: readonly SessionTimelineToolCall[]
  degraded: boolean
  issues: readonly SessionIssue[]
}

export interface SessionConversation {
  entries: readonly SessionConversationEntry[]
  message_count: number
  empty_reason: SessionConversationEmptyReason
  summary: SessionConversationSummary
}

export interface SessionActivityEntry {
  sequence: number
  category: string
  title: string
  summary: string | null
  raw_type: string | null
  mapping_status: SessionTimelineMappingStatus
  occurred_at: string | null
  source_path: string | null
  raw_available: boolean
  raw_payload: unknown
  degraded: boolean
  issues: readonly SessionIssue[]
}

export interface SessionActivity {
  entries: readonly SessionActivityEntry[]
}

export interface SessionDetail {
  id: string
  source_format: string
  created_at: string | null
  updated_at: string | null
  work_context: WorkContext
  selected_model: string | null
  source_state: SessionSourceState
  degraded: boolean
  raw_included: boolean
  issues: readonly SessionIssue[]
  message_snapshots: readonly SessionMessageSnapshot[]
  conversation: SessionConversation
  activity: SessionActivity
  timeline: readonly SessionTimelineEvent[]
}

export interface SessionDetailResponse {
  data: SessionDetail
}

export interface HistorySyncRun {
  id: number
  status: string
  started_at: string | null
  finished_at: string | null
}

export interface HistorySyncCounts {
  processed_count: number
  inserted_count: number
  updated_count: number
  saved_count: number
  skipped_count: number
  failed_count: number
  degraded_count: number
}

export interface HistorySyncResponse {
  data: {
    sync_run: HistorySyncRun
    counts: HistorySyncCounts
  }
}

export interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

export interface SessionApiEnvironment {
  readonly VITE_API_BASE_URL?: string
}

export type SessionApiError =
  | {
      kind: 'config'
      code: 'api_base_url_missing' | 'api_base_url_invalid'
      message: string
      details: {
        env: 'VITE_API_BASE_URL'
        value?: string
      }
    }
  | {
      kind: 'not_found'
      httpStatus: 404
      code: string
      message: string
      details: Record<string, unknown>
    }
  | {
      kind: 'backend'
      httpStatus: number
      code: string
      message: string
      details: Record<string, unknown>
    }
  | {
      kind: 'network'
      code: 'network_error'
      message: string
      details: {
        cause: string
      }
    }

export type SessionApiResult<T> =
  | { status: 'success'; data: T }
  | { status: 'error'; error: SessionApiError }

export interface SessionApiClient {
  fetchSessionIndex(request?: SessionIndexRequest): Promise<SessionApiResult<SessionIndexResponse>>
  fetchSessionDetail(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionApiResult<SessionDetailResponse>>
  fetchSessionDetailWithRaw(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionApiResult<SessionDetailResponse>>
  syncHistory(signal?: AbortSignal): Promise<SessionApiResult<HistorySyncResponse>>
}

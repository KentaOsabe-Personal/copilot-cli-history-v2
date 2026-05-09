import type {
  SessionActivity,
  SessionConversation,
  SessionConversationEntry,
  SessionDetail,
  SessionIssue,
  SessionSummary,
  SessionTimelineEvent,
  SessionTimelineToolCall,
  WorkContext,
} from '../../../../src/features/sessions/api/sessionApi.types.ts'

const populatedWorkContext: WorkContext = {
  cwd: '/workspace/copilot-cli-history',
  git_root: '/workspace/copilot-cli-history',
  repository: 'octo/copilot-cli-history',
  branch: 'main',
}

const missingWorkContext: WorkContext = {
  cwd: null,
  git_root: null,
  repository: null,
  branch: null,
}

const sessionIssue: SessionIssue = {
  code: 'session.partial',
  severity: 'warning',
  message: 'session timeline is incomplete',
  source_path: '/tmp/copilot/session/events.jsonl',
  scope: 'session',
  event_sequence: null,
}

const utteranceIssue: SessionIssue = {
  code: 'event.partial_mapping',
  severity: 'warning',
  message: 'assistant response was partially mapped',
  source_path: '/tmp/copilot/session/events.jsonl',
  scope: 'event',
  event_sequence: 3,
}

const activityIssue: SessionIssue = {
  code: 'activity.partial_mapping',
  severity: 'warning',
  message: 'activity payload is partial',
  source_path: '/tmp/copilot/session/events.jsonl',
  scope: 'event',
  event_sequence: 5,
}

const bashToolCall: SessionTimelineToolCall = {
  name: 'functions.bash',
  arguments_preview: '{"command":"pnpm test -- src/features/sessions"}',
  is_truncated: false,
  status: 'complete',
}

const skillContextToolCall: SessionTimelineToolCall = {
  name: 'skill-context',
  arguments_preview: '{"skill":"session-ui-noise-reduction","notes":["collapse long context"]}',
  is_truncated: true,
  status: 'partial',
}

function buildSummary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  const base: SessionSummary = {
    id: 'current-with-metadata',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: populatedWorkContext,
    selected_model: 'gpt-5-current',
    source_state: 'complete',
    event_count: 6,
    message_snapshot_count: 2,
    conversation_summary: {
      has_conversation: true,
      message_count: 2,
      preview: 'Review the session UI fixtures',
      activity_count: 1,
    },
    degraded: false,
    issues: [],
  }

  return {
    ...base,
    ...overrides,
  }
}

function buildConversation(overrides: Partial<SessionConversation> = {}): SessionConversation {
  const entries: readonly SessionConversationEntry[] = [
    {
      sequence: 1,
      role: 'user',
      content: 'Can you reduce the noisy session UI signals?',
      occurred_at: '2026-04-26T09:00:00Z',
      tool_calls: [],
      degraded: false,
      issues: [],
    },
    {
      sequence: 2,
      role: 'assistant',
      content: 'I will inspect the existing session components first.',
      occurred_at: '2026-04-26T09:00:05Z',
      tool_calls: [bashToolCall],
      degraded: false,
      issues: [],
    },
    {
      sequence: 3,
      role: 'assistant',
      content: 'The detail page should keep utterance issues near the message.',
      occurred_at: '2026-04-26T09:00:12Z',
      tool_calls: [],
      degraded: true,
      issues: [utteranceIssue],
    },
    {
      sequence: 4,
      role: 'assistant',
      content: '',
      occurred_at: '2026-04-26T09:00:20Z',
      tool_calls: [skillContextToolCall],
      degraded: false,
      issues: [],
    },
  ]

  const base: SessionConversation = {
    entries,
    message_count: entries.length,
    empty_reason: null,
    summary: {
      has_conversation: true,
      message_count: entries.length,
      preview: 'Can you reduce the noisy session UI signals?',
      activity_count: 2,
    },
  }

  return {
    ...base,
    ...overrides,
  }
}

function buildActivity(overrides: Partial<SessionActivity> = {}): SessionActivity {
  const base: SessionActivity = {
    entries: [
      {
        sequence: 5,
        category: 'tool_execution',
        title: 'tool.execution_start',
        summary: 'functions.bash / pnpm test',
        raw_type: 'tool.execution_start',
        mapping_status: 'partial',
        occurred_at: '2026-04-26T09:00:03Z',
        source_path: '/tmp/copilot/session/events.jsonl',
        raw_available: true,
        raw_payload: {
          type: 'tool.execution_start',
          tool: 'functions.bash',
        },
        degraded: true,
        issues: [activityIssue],
      },
      {
        sequence: 6,
        category: 'session',
        title: 'session.checkpoint',
        summary: 'checkpoint saved',
        raw_type: 'session.checkpoint',
        mapping_status: 'complete',
        occurred_at: '2026-04-26T09:00:30Z',
        source_path: '/tmp/copilot/session/events.jsonl',
        raw_available: true,
        raw_payload: {
          type: 'session.checkpoint',
        },
        degraded: false,
        issues: [],
      },
    ],
  }

  return {
    ...base,
    ...overrides,
  }
}

function buildTimeline(conversation: SessionConversation, activity: SessionActivity): readonly SessionTimelineEvent[] {
  const messageEvents: readonly SessionTimelineEvent[] = conversation.entries.map((entry) => ({
    sequence: entry.sequence,
    kind: 'message',
    mapping_status: entry.degraded ? 'partial' : 'complete',
    raw_type: `${entry.role}.message`,
    occurred_at: entry.occurred_at,
    role: entry.role,
    content: entry.content,
    tool_calls: entry.tool_calls,
    detail: null,
    raw_payload: {
      role: entry.role,
      content: entry.content,
      tool_calls: entry.tool_calls,
    },
    degraded: entry.degraded,
    issues: entry.issues,
  }))

  const activityEvents: readonly SessionTimelineEvent[] = activity.entries.map((entry) => ({
    sequence: entry.sequence,
    kind: 'detail',
    mapping_status: entry.mapping_status,
    raw_type: entry.raw_type,
    occurred_at: entry.occurred_at,
    role: null,
    content: null,
    tool_calls: [],
    detail: {
      category: entry.category,
      title: entry.title,
      body: entry.summary,
    },
    raw_payload: entry.raw_payload,
    degraded: entry.degraded,
    issues: entry.issues,
  }))

  return [...messageEvents, ...activityEvents].sort((left, right) => left.sequence - right.sequence)
}

function buildDetail(overrides: Partial<SessionDetail> = {}): SessionDetail {
  const conversation = overrides.conversation ?? buildConversation()
  const activity = overrides.activity ?? buildActivity()
  const base: SessionDetail = {
    id: 'detail-interaction-surface',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: populatedWorkContext,
    selected_model: 'gpt-5-current',
    source_state: 'degraded',
    degraded: true,
    raw_included: false,
    issues: [sessionIssue],
    message_snapshots: [],
    conversation,
    activity,
    timeline: buildTimeline(conversation, activity),
  }

  return {
    ...base,
    ...overrides,
  }
}

const emptyConversation: SessionConversation = {
  entries: [],
  message_count: 0,
  empty_reason: 'no_conversation_messages',
  summary: {
    has_conversation: false,
    message_count: 0,
    preview: null,
    activity_count: 0,
  },
}

const workspaceOnlyConversation: SessionConversation = {
  ...emptyConversation,
  empty_reason: 'events_unavailable',
}

export const sessionUiSummaryScenarios = {
  withWorkContextAndModel: buildSummary(),
  missingWorkContextAndModel: buildSummary({
    id: 'legacy-missing-metadata',
    source_format: 'legacy',
    work_context: missingWorkContext,
    selected_model: null,
  }),
  currentWithoutModel: buildSummary({
    id: 'current-without-model',
    selected_model: null,
  }),
  legacyWithModel: buildSummary({
    id: 'legacy-with-model',
    source_format: 'legacy',
    selected_model: 'gpt-5-legacy',
  }),
  legacyWithoutModel: buildSummary({
    id: 'legacy-without-model',
    source_format: 'legacy',
    selected_model: null,
  }),
  metadataOnly: buildSummary({
    id: 'metadata-only',
    conversation_summary: {
      has_conversation: false,
      message_count: 0,
      preview: null,
      activity_count: 0,
    },
    event_count: 1,
    message_snapshot_count: 0,
  }),
  workspaceOnly: buildSummary({
    id: 'workspace-only',
    source_state: 'workspace_only',
    conversation_summary: {
      has_conversation: false,
      message_count: 0,
      preview: null,
      activity_count: 0,
    },
    event_count: 0,
    message_snapshot_count: 0,
  }),
  degraded: buildSummary({
    id: 'degraded-session',
    source_state: 'degraded',
    degraded: true,
    issues: [sessionIssue],
  }),
} satisfies Record<string, SessionSummary>

export const sessionUiDetailScenarios = {
  interactionSurface: buildDetail(),
  metadataOnly: buildDetail({
    id: 'detail-metadata-only',
    source_state: 'complete',
    degraded: false,
    issues: [],
    conversation: emptyConversation,
    activity: { entries: [] },
    timeline: [],
  }),
  workspaceOnly: buildDetail({
    id: 'detail-workspace-only',
    source_state: 'workspace_only',
    degraded: false,
    issues: [],
    conversation: workspaceOnlyConversation,
    activity: { entries: [] },
    timeline: [],
  }),
  missingWorkContextAndModel: buildDetail({
    id: 'detail-missing-metadata',
    source_format: 'legacy',
    work_context: missingWorkContext,
    selected_model: null,
    source_state: 'complete',
    degraded: false,
    issues: [],
  }),
} satisfies Record<string, SessionDetail>

export { buildDetail as buildSessionUiDetail, buildSummary as buildSessionUiSummary }

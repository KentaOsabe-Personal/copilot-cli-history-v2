import { describe, expect, it } from 'vitest'

import type { SessionActivityEntry, SessionTimelineEvent } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import {
  deriveConversationEntriesFromTimeline,
  formatActivityContent,
  formatTimelineContent,
} from '../../../../src/features/sessions/presentation/timelineContent.ts'

interface TimelineToolCallSummary {
  name: string | null
  arguments_preview: string | null
  is_truncated: boolean
  status: 'complete' | 'partial'
}

interface TimelineDetailSummary {
  category: string
  title: string
  body: string | null
}

type TimelineEventForContent = SessionTimelineEvent & {
  mapping_status: 'complete' | 'partial'
  tool_calls: readonly TimelineToolCallSummary[]
  detail: TimelineDetailSummary | null
}

function buildEvent(overrides: Partial<TimelineEventForContent> = {}): TimelineEventForContent {
  return {
    sequence: 1,
    kind: 'message',
    mapping_status: 'complete',
    raw_type: 'assistant_message',
    occurred_at: '2026-04-26T09:00:02Z',
    role: 'assistant',
    content: 'plain text',
    tool_calls: [],
    detail: null,
    raw_payload: {},
    degraded: false,
    issues: [],
    ...overrides,
  }
}

describe('formatTimelineContent', () => {
  /**
   * 概要・目的: 「extracts tool hints from canonical helper fields and preserves text/code order」を通じて、検索・日付条件と
   *   query 組み立てを検証する。
   * テストケース: 「extracts tool hints from canonical helper fields and preserves text/code order」の条件・入力・操作を実行する。
   * 期待値: 「extracts tool hints from canonical helper fields and preserves text/code order」で示す状態または振る舞いが成立すること。
   */
  it('extracts tool hints from canonical helper fields and preserves text/code order', () => {
    const event = buildEvent({
      content: 'Before code\n```ts\nconst answer = 42\n```\nAfter code',
      tool_calls: [
        {
          name: 'functions.bash',
          arguments_preview: '{"command":"pwd"}',
          is_truncated: false,
          status: 'complete',
        },
      ],
    })

    expect(formatTimelineContent(event)).toEqual({
      blocks: [
        {
          kind: 'text',
          text: 'Before code\n',
        },
        {
          kind: 'code',
          language: 'ts',
          code: 'const answer = 42\n',
        },
        {
          kind: 'text',
          text: '\nAfter code',
        },
        {
          kind: 'tool_hint',
          name: 'functions.bash',
          argumentsPreview: '{"command":"pwd"}',
          isTruncated: false,
          status: 'complete',
          argumentsDefaultCollapsed: true,
          collapseReason: 'arguments_preview',
        },
      ],
    })
  })

  /**
   * 概要・目的: 「keeps partial tool summaries even when only a subset of fields is
   *   available」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「keeps partial tool summaries even when only a subset of fields is available」の条件・入力・操作を実行する。
   * 期待値: partial tool summaries even when only a subset of fields is available が維持されること。
   */
  it('keeps partial tool summaries even when only a subset of fields is available', () => {
    const event = buildEvent({
      content: null,
      tool_calls: [
        {
          name: null,
          arguments_preview: '{"input":"y"}',
          is_truncated: true,
          status: 'partial',
        },
      ],
    })

    expect(formatTimelineContent(event)).toEqual({
      blocks: [
        {
          kind: 'tool_hint',
          name: null,
          argumentsPreview: '{"input":"y"}',
          isTruncated: true,
          status: 'partial',
          argumentsDefaultCollapsed: true,
          collapseReason: 'truncated_arguments',
        },
      ],
    })
  })

  /**
   * 概要・目的: 「formats non-message detail summaries as dedicated blocks」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「formats non-message detail summaries as dedicated blocks」の条件・入力・操作を実行する。
   * 期待値: non-message detail summaries as dedicated blocks が表示用に整形されること。
   */
  it('formats non-message detail summaries as dedicated blocks', () => {
    const event = buildEvent({
      kind: 'detail',
      role: null,
      content: null,
      detail: {
        category: 'tool_execution',
        title: 'tool.execution_start',
        body: 'functions.bash / tool-1',
      },
    })

    expect(formatTimelineContent(event)).toEqual({
      blocks: [
        {
          kind: 'detail',
          category: 'tool_execution',
          title: 'tool.execution_start',
          body: 'functions.bash / tool-1',
        },
      ],
    })
  })
})

function buildActivity(overrides: Partial<SessionActivityEntry> = {}): SessionActivityEntry {
  return {
    sequence: 4,
    category: 'unknown',
    title: 'mystery.event',
    summary: 'unknown payload was retained',
    raw_type: 'mystery.event',
    mapping_status: 'partial',
    occurred_at: '2026-04-26T09:00:04Z',
    source_path: '/tmp/session/events.jsonl',
    raw_available: true,
    raw_payload: null,
    degraded: true,
    issues: [],
    ...overrides,
  }
}

describe('formatActivityContent', () => {
  /**
   * 概要・目的: 「formats internal activity without message content blocks」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「formats internal activity without message content blocks」の条件・入力・操作を実行する。
   * 期待値: internal activity without message content blocks が表示用に整形されること。
   */
  it('formats internal activity without message content blocks', () => {
    expect(formatActivityContent(buildActivity())).toEqual({
      sequence: 4,
      category: 'unknown',
      title: 'mystery.event',
      summary: 'unknown payload was retained',
      rawType: 'mystery.event',
      mappingStatus: 'partial',
      occurredAt: '2026-04-26T09:00:04Z',
      sourcePath: '/tmp/session/events.jsonl',
      rawAvailable: true,
      degraded: true,
      issues: [],
      blocks: [
        {
          kind: 'detail',
          category: 'unknown',
          title: 'mystery.event',
          body: 'unknown payload was retained',
        },
      ],
    })
  })
})

describe('deriveConversationEntriesFromTimeline', () => {
  /**
   * 概要・目的: 「falls back to non-empty user and assistant messages only」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「falls back to non-empty user and assistant messages only」の条件・入力・操作を実行する。
   * 期待値: non-empty user and assistant messages only に fallback すること。
   */
  it('falls back to non-empty user and assistant messages only', () => {
    const timeline: readonly SessionTimelineEvent[] = [
      buildEvent({
        sequence: 1,
        role: 'user',
        content: 'hello',
      }),
      buildEvent({
        sequence: 2,
        role: 'assistant',
        content: '',
        tool_calls: [
          {
            name: 'functions.bash',
            arguments_preview: '{"command":"pwd"}',
            is_truncated: false,
            status: 'complete',
          },
        ],
      }),
      buildEvent({
        sequence: 3,
        kind: 'detail',
        role: null,
        content: 'tool output',
      }),
      buildEvent({
        sequence: 4,
        role: 'assistant',
        content: 'answer',
      }),
    ]

    expect(deriveConversationEntriesFromTimeline(timeline).map((entry) => ({
      sequence: entry.sequence,
      role: entry.role,
      content: entry.content,
    }))).toEqual([
      {
        sequence: 1,
        role: 'user',
        content: 'hello',
      },
      {
        sequence: 4,
        role: 'assistant',
        content: 'answer',
      },
    ])
  })
})

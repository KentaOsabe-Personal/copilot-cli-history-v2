import { render, screen } from '@testing-library/react'

import type { SessionTimelineEvent } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import TimelineEntry from '../../../../src/features/sessions/components/TimelineEntry.tsx'

function buildEvent(overrides: Partial<SessionTimelineEvent> = {}): SessionTimelineEvent {
  return {
    sequence: 2,
    kind: 'detail',
    mapping_status: 'partial',
    raw_type: 'tool.execution_start',
    occurred_at: null,
    role: null,
    content: null,
    tool_calls: [],
    detail: {
      category: 'tool_execution',
      title: 'tool.execution_start',
      body: 'functions.bash / tool-1',
    },
    raw_payload: {
      type: 'tool.execution_start',
    },
    degraded: true,
    issues: [
      {
        code: 'event.partial_mapping',
        severity: 'warning',
        message: 'event payload matched partially',
        source_path: '/tmp/current-schema-degraded/events.jsonl',
        scope: 'event',
        event_sequence: 2,
      },
    ],
    ...overrides,
  }
}

describe('TimelineEntry', () => {
  /**
   * 概要・目的: 「keeps kind, partial state, and issue explanation distinct for degraded non-message
   *   events」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps kind, partial state, and issue explanation distinct for degraded non-message
   *   events」の条件・入力・操作を実行する。
   * 期待値: kind, partial state, が維持され、issue explanation distinct for degraded non-message eventsこと。
   */
  it('keeps kind, partial state, and issue explanation distinct for degraded non-message events', () => {
    render(<TimelineEntry event={buildEvent()} />)

    expect(screen.getByRole('heading', { level: 4, name: 'イベント #2' })).toBeInTheDocument()
    expect(screen.getByText('detail')).toBeInTheDocument()
    expect(screen.getByText('partial')).toBeInTheDocument()
    expect(screen.queryByText('assistant')).not.toBeInTheDocument()
    expect(screen.getByText('詳細イベント')).toBeInTheDocument()
    expect(screen.getAllByText('tool.execution_start')).toHaveLength(2)
    expect(screen.getByText('functions.bash / tool-1')).toBeInTheDocument()
    expect(screen.getAllByText('イベント #2')).toHaveLength(2)
    expect(screen.getByText('event payload matched partially')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps unknown events readable without inventing a message role」を通じて、reader と fixture
   *   の読取・劣化時の扱いを検証する。
   * テストケース: 「keeps unknown events readable without inventing a message role」の条件・入力・操作を実行する。
   * 期待値: unknown events readable without inventing a message role が維持されること。
   */
  it('keeps unknown events readable without inventing a message role', () => {
    render(
      <TimelineEntry
        event={buildEvent({
          sequence: 4,
          kind: 'unknown',
          mapping_status: 'complete',
          raw_type: 'mystery.event',
          occurred_at: '2026-04-26T09:00:03Z',
          content: 'unknown payload stays readable',
          detail: null,
          degraded: false,
          issues: [],
        })}
      />,
    )

    expect(screen.getByText('unknown')).toBeInTheDocument()
    expect(screen.queryByText('partial')).not.toBeInTheDocument()
    expect(screen.queryByText('assistant')).not.toBeInTheDocument()
    expect(screen.getByText('unknown payload stays readable')).toBeInTheDocument()
  })
})

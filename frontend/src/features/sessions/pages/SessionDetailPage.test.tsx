import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SessionDetail } from '../api/sessionApi.types.ts'
import { useSessionDetail } from '../hooks/useSessionDetail.ts'
import SessionDetailPage from './SessionDetailPage.tsx'

vi.mock('../hooks/useSessionDetail.ts', () => ({
  useSessionDetail: vi.fn(),
}))

const mockedUseSessionDetail = vi.mocked(useSessionDetail)
const requestRaw = vi.fn()

function buildDetail(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: 'session-123',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: {
      cwd: '/workspace/session-123',
      git_root: '/workspace/session-123',
      repository: 'octo/example',
      branch: 'main',
    },
    selected_model: 'gpt-5.4',
    source_state: 'degraded',
    degraded: true,
    raw_included: false,
    issues: [
      {
        code: 'session.partial',
        severity: 'warning',
        message: 'session timeline is incomplete',
        source_path: '/tmp/session.json',
        scope: 'session',
        event_sequence: null,
      },
    ],
    message_snapshots: [],
    conversation: {
      entries: [
        {
          sequence: 1,
          role: 'assistant',
          content: '説明です\n```ts\nconst answer = 42\n```',
          occurred_at: '2026-04-26T09:00:02Z',
          tool_calls: [
            {
              name: 'functions.bash',
              arguments_preview: '{"command":"pwd"}',
              is_truncated: false,
              status: 'complete',
            },
          ],
          degraded: false,
          issues: [],
        },
      ],
      message_count: 1,
      empty_reason: null,
      summary: {
        has_conversation: true,
        message_count: 1,
        preview: '説明です',
        activity_count: 2,
      },
    },
    activity: {
      entries: [
        {
          sequence: 2,
          category: 'tool_execution',
          title: 'tool.execution_start',
          summary: 'functions.bash / tool-1',
          raw_type: 'tool.execution_start',
          mapping_status: 'partial',
          occurred_at: null,
          source_path: null,
          raw_available: true,
          raw_payload: null,
          degraded: true,
          issues: [
            {
              code: 'event.partial',
              severity: 'warning',
              message: 'event payload is partial',
              source_path: null,
              scope: 'event',
              event_sequence: 2,
            },
          ],
        },
        {
          sequence: 3,
          category: 'unknown',
          title: 'mystery_event',
          summary: 'unknown payload stays readable',
          raw_type: 'mystery_event',
          mapping_status: 'complete',
          occurred_at: '2026-04-26T09:00:03Z',
          source_path: null,
          raw_available: true,
          raw_payload: null,
          degraded: false,
          issues: [],
        },
      ],
    },
    timeline: [
      {
        sequence: 1,
        kind: 'message',
        mapping_status: 'complete',
        raw_type: 'assistant_message',
        occurred_at: '2026-04-26T09:00:02Z',
        role: 'assistant',
        content: '説明です\n```ts\nconst answer = 42\n```',
        tool_calls: [
          {
            name: 'functions.bash',
            arguments_preview: '{"command":"pwd"}',
            is_truncated: false,
            status: 'complete',
          },
        ],
        detail: null,
        raw_payload: {},
        degraded: false,
        issues: [],
      },
      {
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
            code: 'event.partial',
            severity: 'warning',
            message: 'event payload is partial',
            source_path: null,
            scope: 'event',
            event_sequence: 2,
          },
        ],
      },
      {
        sequence: 3,
        kind: 'unknown',
        mapping_status: 'complete',
        raw_type: 'mystery_event',
        occurred_at: '2026-04-26T09:00:03Z',
        role: null,
        content: 'unknown payload stays readable',
        tool_calls: [],
        detail: null,
        raw_payload: {
          toolRequests: [
            {
              label: 'write_bash',
            },
          ],
        },
        degraded: false,
        issues: [],
      },
    ],
    ...overrides,
  }
}

function renderDetailPage(initialEntry = '/sessions/session-123') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SessionDetailPage', () => {
  beforeEach(() => {
    mockedUseSessionDetail.mockReset()
    requestRaw.mockReset()
  })

  it('renders a loading panel while the detail is being fetched', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'loading',
        sessionId: 'session-123',
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.getByRole('heading', { name: 'セッション詳細' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション詳細を読み込んでいます' })).toBeInTheDocument()
  })

  it('renders header metadata, session issues, and timeline entries for a degraded success response', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail(),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.getAllByText('session-123').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'セッション一覧へ戻る' })).toHaveAttribute('href', '/')
    expect(screen.getAllByText('一部欠損あり').length).toBeGreaterThan(0)
    expect(screen.getByText('2026-04-26 18:05:00 JST')).toBeInTheDocument()
    expect(screen.getByText('2026-04-26 18:00:02 JST')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '会話' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '内部 activity' })).toBeInTheDocument()
    expect(screen.getByText('assistant')).toBeInTheDocument()
    expect(screen.queryByText('イベント #1')).not.toBeInTheDocument()
    expect(screen.getByText('説明です')).toBeInTheDocument()
    expect(screen.getByText('const answer = 42')).toBeInTheDocument()
    expect(screen.getByText('functions.bash')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'セッションの issue を表示' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '内部 activity を表示' })).toBeInTheDocument()
    expect(screen.queryByText('session timeline is incomplete')).not.toBeInTheDocument()
    expect(screen.queryByText('functions.bash / tool-1')).not.toBeInTheDocument()
  })

  it('omits placeholder-only work context and model metadata from the detail header', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail({
          work_context: {
            cwd: null,
            git_root: null,
            repository: null,
            branch: null,
          },
          selected_model: null,
        }),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.queryByText('作業コンテキスト不明')).not.toBeInTheDocument()
    expect(screen.queryByText('モデル不明')).not.toBeInTheDocument()
  })

  it('applies a wrap-safe class to the route-level session id', () => {
    const longSessionId =
      'route-session-id-with-an-extremely-long-identifier-that-should-wrap-without-requiring-page-scroll'

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: longSessionId,
        rawStatus: 'idle',
        detail: buildDetail({
          id: longSessionId,
        }),
      },
      requestRaw,
    })

    renderDetailPage(`/sessions/${longSessionId}`)

    expect(screen.getAllByText(longSessionId)[0]).toHaveClass('break-all')
  })

  it('keeps tool, code, partial, and unknown timeline events readable in sequence order', async () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail(),
      },
      requestRaw,
    })

    renderDetailPage()

    const user = userEvent.setup()
    const activitySection = screen.getByRole('heading', { name: '内部 activity' }).closest('section')

    expect(activitySection).not.toBeNull()
    expect(within(activitySection as HTMLElement).queryByRole('heading', { level: 4 })).not.toBeInTheDocument()
    expect(screen.queryByText('functions.bash / tool-1')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '内部 activity を表示' }))

    expect(
      within(activitySection as HTMLElement).getAllByRole('heading', { level: 4 }).map((node) => node.textContent),
    ).toEqual([
      'Activity #2',
      'Activity #3',
    ])
    expect(screen.queryByText('message')).not.toBeInTheDocument()
    expect(screen.getByText('partial')).toBeInTheDocument()
    expect(screen.getAllByText('unknown').length).toBeGreaterThan(0)
    expect(screen.getByText('const answer = 42')).toBeInTheDocument()
    expect(screen.getByText('functions.bash')).toBeInTheDocument()
    expect(screen.getByText('functions.bash / tool-1')).toBeInTheDocument()
    expect(screen.getByText('unknown payload stays readable')).toBeInTheDocument()
    expect(screen.queryByText('write_bash')).not.toBeInTheDocument()
  })

  it('renders a clean legacy session in the same detail flow without schema-specific UI', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'legacy-session-123',
        rawStatus: 'idle',
        detail: buildDetail({
          id: 'legacy-session-123',
          source_format: 'legacy',
          degraded: false,
          issues: [],
          conversation: {
            entries: [
              {
                sequence: 1,
                role: 'assistant',
                content: 'legacy transcript remains readable',
                occurred_at: '2026-04-26T08:59:00Z',
                tool_calls: [],
                degraded: false,
                issues: [],
              },
            ],
            message_count: 1,
            empty_reason: null,
            summary: {
              has_conversation: true,
              message_count: 1,
              preview: 'legacy transcript remains readable',
              activity_count: 0,
            },
          },
          activity: {
            entries: [],
          },
          timeline: [
            {
              sequence: 1,
              kind: 'message',
              mapping_status: 'complete',
              raw_type: 'assistant_message',
              occurred_at: '2026-04-26T08:59:00Z',
              role: 'assistant',
              content: 'legacy transcript remains readable',
              tool_calls: [],
              detail: null,
              raw_payload: {
                type: 'assistant_message',
              },
              degraded: false,
              issues: [],
            },
          ],
        }),
      },
      requestRaw,
    })

    renderDetailPage('/sessions/legacy-session-123')

    expect(screen.getAllByText('legacy-session-123').length).toBeGreaterThan(0)
    expect(screen.getByText('assistant')).toBeInTheDocument()
    expect(screen.getByText('legacy transcript remains readable')).toBeInTheDocument()
    expect(screen.queryByText('partial')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
    expect(screen.queryByText('workspace-only')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'セッションの issue' })).not.toBeInTheDocument()
  })

  it('keeps other conversation and activity details readable even when one entry lacks renderable body content', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail({
          conversation: {
            entries: [
              {
                sequence: 1,
                role: 'assistant',
                content: '',
                occurred_at: '2026-04-26T09:00:00Z',
                tool_calls: [],
                degraded: true,
                issues: [
                  {
                    code: 'message.empty',
                    severity: 'warning',
                    message: 'entry body missing',
                    source_path: null,
                    scope: 'event',
                    event_sequence: 1,
                  },
                ],
              },
              {
                sequence: 2,
                role: 'user',
                content: 'follow-up question still visible',
                occurred_at: '2026-04-26T09:00:04Z',
                tool_calls: [],
                degraded: false,
                issues: [],
              },
            ],
            message_count: 2,
            empty_reason: null,
            summary: {
              has_conversation: true,
              message_count: 2,
              preview: 'follow-up question still visible',
              activity_count: 2,
            },
          },
        }),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.getByText('発話 #1')).toBeInTheDocument()
    expect(screen.getByText('entry body missing')).toBeInTheDocument()
    expect(screen.getByText('follow-up question still visible')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '内部 activity' })).toBeInTheDocument()
  })

  it('preserves conversation, activity, degraded, and issue metadata for legacy detail responses too', async () => {
    const user = userEvent.setup()

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'legacy-session-456',
        rawStatus: 'idle',
        detail: buildDetail({
          id: 'legacy-session-456',
          source_format: 'legacy',
          source_state: 'degraded',
          degraded: true,
          issues: [
            {
              code: 'legacy.partial',
              severity: 'warning',
              message: 'legacy history is incomplete',
              source_path: '/tmp/legacy.json',
              scope: 'session',
              event_sequence: null,
            },
          ],
          conversation: {
            entries: [
              {
                sequence: 1,
                role: 'assistant',
                content: 'legacy transcript remains readable',
                occurred_at: '2026-04-26T08:59:00Z',
                tool_calls: [],
                degraded: true,
                issues: [
                  {
                    code: 'legacy.message.partial',
                    severity: 'warning',
                    message: 'legacy assistant message is partial',
                    source_path: null,
                    scope: 'event',
                    event_sequence: 1,
                  },
                ],
              },
            ],
            message_count: 1,
            empty_reason: null,
            summary: {
              has_conversation: true,
              message_count: 1,
              preview: 'legacy transcript remains readable',
              activity_count: 1,
            },
          },
          activity: {
            entries: [
              {
                sequence: 2,
                category: 'tool_execution',
                title: 'tool.execution_start',
                summary: 'legacy tool execution stays readable',
                raw_type: 'tool.execution_start',
                mapping_status: 'partial',
                occurred_at: '2026-04-26T08:59:02Z',
                source_path: null,
                raw_available: true,
                raw_payload: null,
                degraded: true,
                issues: [
                  {
                    code: 'legacy.activity.partial',
                    severity: 'warning',
                    message: 'legacy activity is partial',
                    source_path: null,
                    scope: 'event',
                    event_sequence: 2,
                  },
                ],
              },
            ],
          },
        }),
      },
      requestRaw,
    })

    renderDetailPage('/sessions/legacy-session-456')

    expect(screen.getAllByText('legacy-session-456').length).toBeGreaterThan(0)
    expect(screen.getAllByText('一部欠損あり').length).toBeGreaterThan(0)
    expect(screen.getByText('legacy transcript remains readable')).toBeInTheDocument()
    expect(screen.getByText('legacy assistant message is partial')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'セッションの issue を表示' }))
    await user.click(screen.getByRole('button', { name: '内部 activity を表示' }))

    expect(screen.getByText('legacy history is incomplete')).toBeInTheDocument()
    expect(screen.getByText('legacy tool execution stays readable')).toBeInTheDocument()
    expect(screen.getByText('legacy activity is partial')).toBeInTheDocument()
    expect(screen.getByText('2026-04-26 17:59:02 JST')).toBeInTheDocument()
  })

  it('renders a dedicated not found panel with a link back to the index', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'not_found',
        sessionId: 'missing-session',
      },
      requestRaw,
    })

    renderDetailPage('/sessions/missing-session')

    expect(screen.getByRole('heading', { name: 'セッションが見つかりません' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'セッション一覧へ戻る' })).toHaveAttribute('href', '/')
  })

  it('renders an error panel with a link back to the index', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'error',
        sessionId: 'session-123',
        error: {
          kind: 'backend',
          httpStatus: 503,
          code: 'root_missing',
          message: 'history root does not exist',
          details: {
            path: '/tmp/.copilot',
          },
        },
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.getByRole('heading', { name: 'セッション詳細を表示できません' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'セッション一覧へ戻る' })).toHaveAttribute('href', '/')
  })

  it('renders an explicit empty conversation state instead of filling the main area with activity', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail({
          conversation: {
            entries: [],
            message_count: 0,
            empty_reason: 'no_conversation_messages',
            summary: {
              has_conversation: false,
              message_count: 0,
              preview: null,
              activity_count: 2,
            },
          },
        }),
      },
      requestRaw,
    })

    renderDetailPage()

    const conversationSection = screen.getByRole('heading', { name: '会話' }).closest('section')

    expect(conversationSection).not.toBeNull()
    expect(within(conversationSection as HTMLElement).getAllByText('表示できる会話本文はありません').length).toBeGreaterThan(0)
    expect(within(conversationSection as HTMLElement).queryByText('functions.bash / tool-1')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '内部 activity' })).toBeInTheDocument()
  })

  it('requests raw detail only from the explicit raw action and keeps raw status visible', async () => {
    const user = userEvent.setup()

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail(),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.queryByRole('button', { name: 'Raw を取得' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '内部 activity を表示' }))
    await user.click(screen.getByRole('button', { name: 'Raw を取得' }))

    expect(requestRaw).toHaveBeenCalledTimes(1)

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'included',
        detail: buildDetail({
          raw_included: true,
        }),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.getByRole('button', { name: '内部 activity を表示' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '内部 activity を表示' }))
    expect(screen.getByText('raw included')).toBeInTheDocument()
  })

  it('renders disclosures after the conversation and expands session issues only on demand', async () => {
    const user = userEvent.setup()

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail(),
      },
      requestRaw,
    })

    renderDetailPage()

    const conversationHeading = screen.getByRole('heading', { name: '会話' })
    const sessionIssueHeading = screen.getByRole('heading', { name: 'セッションの issue' })
    const activityHeading = screen.getByRole('heading', { name: '内部 activity' })

    expect(conversationHeading.compareDocumentPosition(sessionIssueHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(sessionIssueHeading.compareDocumentPosition(activityHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByText('session timeline is incomplete')).not.toBeInTheDocument()
    expect(screen.queryByText('セッション全体')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'セッションの issue を表示' }))

    expect(screen.getByText('session timeline is incomplete')).toBeInTheDocument()
    expect(screen.getAllByText('警告').length).toBeGreaterThan(0)
    expect(screen.getByText('セッション全体')).toBeInTheDocument()
  })

  it('keeps the detail page read-only without edit, delete, send, share, timezone, or dedicated raw-viewer controls', () => {
    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail(),
      },
      requestRaw,
    })

    renderDetailPage()

    expect(screen.queryByRole('button', { name: /編集|削除|送信|共有/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /編集|削除|送信|共有/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: /timezone|タイムゾーン/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /timezone|タイムゾーン/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /raw viewer|raw payload viewer/i })).not.toBeInTheDocument()
  })
})

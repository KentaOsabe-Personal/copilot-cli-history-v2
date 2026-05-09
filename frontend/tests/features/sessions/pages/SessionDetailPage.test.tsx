import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SessionDetail } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import { useSessionDetail } from '../../../../src/features/sessions/hooks/useSessionDetail.ts'
import SessionDetailPage from '../../../../src/features/sessions/pages/SessionDetailPage.tsx'

vi.mock('../../../../src/features/sessions/hooks/useSessionDetail.ts', () => ({
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

  /**
   * 概要・目的: 「renders a loading panel while the detail is being fetched」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「renders a loading panel while the detail is being fetched」の条件・入力・操作を実行する。
   * 期待値: a loading panel while the detail is being fetched が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「renders header metadata, session issues, and timeline entries for a degraded success
   *   response」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders header metadata, session issues, and timeline entries for a degraded success
   *   response」の条件・入力・操作を実行する。
   * 期待値: header metadata, session issues, が表示され、timeline entries for a degraded success responseこと。
   */
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

  /**
   * 概要・目的: 「omits placeholder-only work context and model metadata from the detail
   *   header」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「omits placeholder-only work context and model metadata from the detail header」の条件・入力・操作を実行する。
   * 期待値: placeholder-only work context and model metadata from the detail header が含まれないこと。
   */
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

  /**
   * 概要・目的: 「starts tool-only conversation entries hidden by default in the detail
   *   page」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「starts tool-only conversation entries hidden by default in the detail page」の条件・入力・操作を実行する。
   * 期待値: 「starts tool-only conversation entries hidden by default in the detail page」で示す状態または振る舞いが成立すること。
   */
  it('starts tool-only conversation entries hidden by default in the detail page', async () => {
    const user = userEvent.setup()

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail({
          conversation: {
            entries: [
              {
                sequence: 4,
                role: 'assistant',
                content: '',
                occurred_at: '2026-04-26T09:00:04Z',
                tool_calls: [
                  {
                    name: 'functions.view',
                    arguments_preview: '{"path":"/tmp/session.json"}',
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
              preview: null,
              activity_count: 0,
            },
          },
          activity: {
            entries: [],
          },
          timeline: [],
        }),
      },
      requestRaw,
    })

    renderDetailPage()

    const entry = screen.getByTestId('conversation-entry-4')

    expect(screen.getByRole('button', { name: '発話 #4 を表示' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(entry).not.toHaveTextContent('functions.view')
    expect(entry).not.toHaveTextContent('{"path":"/tmp/session.json"}')

    await user.click(screen.getByRole('button', { name: '発話 #4 を表示' }))

    expect(screen.getByRole('button', { name: '発話 #4 を非表示' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(entry).toHaveTextContent('functions.view')
  })

  /**
   * 概要・目的: 「applies a wrap-safe class to the route-level session id」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「applies a wrap-safe class to the route-level session id」の条件・入力・操作を実行する。
   * 期待値: a wrap-safe class to the route-level session id が適用されること。
   */
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

  /**
   * 概要・目的: 「keeps overflow-sensitive detail surfaces block-local and wrap-safe in the rendered
   *   page」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps overflow-sensitive detail surfaces block-local and wrap-safe in the rendered
   *   page」の条件・入力・操作を実行する。
   * 期待値: overflow-sensitive detail surfaces block-local が維持され、wrap-safe in the rendered pageこと。
   */
  it('keeps overflow-sensitive detail surfaces block-local and wrap-safe in the rendered page', async () => {
    const user = userEvent.setup()
    const longSessionId =
      'detail-session-id-with-an-extremely-long-identifier-that-should-wrap-without-requiring-page-scroll'
    const longRepositoryLabel =
      'octo/copilot-cli-history-with-an-exceptionally-long-repository-name-for-wrap-testing @ feature/detail-page-overflow-safe-rendering-with-very-long-branch-identifiers'
    const longProse =
      'Readable prose keeps aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapWithinTheTimelineSurface'
    const longIssueMessage =
      'issue-message-with-aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapInsideTheDetailSurface'
    const longIssuePath =
      '/tmp/copilot/session/a/very/long/path/with/no/natural/breakpoints/that/should/not/overflow/the/page/events.jsonl'
    const codeLine =
      'const extremelyLongValue = "super-long-token-without-natural-breakpoints-super-long-token-without-natural-breakpoints"'
    const rawPayloadToken =
      'raw-payload-with-a-very-long-token-without-natural-breakpoints-raw-payload-with-a-very-long-token'

    mockedUseSessionDetail.mockReturnValue({
      state: {
        status: 'success',
        sessionId: longSessionId,
        rawStatus: 'included',
        detail: buildDetail({
          id: longSessionId,
          raw_included: true,
          work_context: {
            cwd: '/workspace/some/really/long/path/that/should/not/force/page-level-horizontal-scroll',
            git_root:
              '/workspace/some/really/long/path/that/should/not/force/page-level-horizontal-scroll',
            repository:
              'octo/copilot-cli-history-with-an-exceptionally-long-repository-name-for-wrap-testing',
            branch:
              'feature/detail-page-overflow-safe-rendering-with-very-long-branch-identifiers',
          },
          selected_model: 'gpt-5.4-with-a-very-long-suffix-for-overflow-checking',
          issues: [
            {
              code: 'session.partial',
              severity: 'warning',
              message: longIssueMessage,
              source_path: longIssuePath,
              scope: 'session',
              event_sequence: null,
            },
          ],
          conversation: {
            entries: [
              {
                sequence: 1,
                role: 'assistant',
                content: `${longProse}\n\`\`\`ts\n${codeLine}\n\`\`\``,
                occurred_at: '2026-04-26T09:00:02Z',
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
              preview: longProse,
              activity_count: 1,
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
                occurred_at: '2026-04-26T09:00:03Z',
                source_path: longIssuePath,
                raw_available: true,
                raw_payload: {
                  token: rawPayloadToken,
                },
                degraded: true,
                issues: [],
              },
            ],
          },
        }),
      },
      requestRaw,
    })

    renderDetailPage(`/sessions/${longSessionId}`)

    const routeSessionId = screen
      .getAllByText(longSessionId)
      .find((element) => element.tagName.toLowerCase() === 'p')

    expect(routeSessionId).toHaveClass('break-all')
    expect(screen.getByText(longRepositoryLabel)).toHaveClass('break-words')
    expect(screen.getByText(longProse)).toHaveClass('whitespace-pre-wrap', 'break-words')
    expect(screen.getByText(codeLine).closest('pre')).toHaveClass('overflow-x-auto', 'whitespace-pre')

    await user.click(screen.getByRole('button', { name: 'セッションの issue を表示' }))
    await user.click(screen.getByRole('button', { name: '内部 activity を表示' }))

    expect(screen.getByText(longIssueMessage)).toHaveClass('whitespace-pre-wrap', 'break-words')
    expect(screen.getByText(longIssuePath)).toHaveClass('break-all')
    expect(
      screen.getByText((content) => content.includes(rawPayloadToken)).closest('pre'),
    ).toHaveClass(
      'overflow-x-auto',
      'whitespace-pre',
    )
  })

  /**
   * 概要・目的: 「keeps tool, code, partial, and unknown timeline events readable in sequence order」を通じて、reader と
   *   fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「keeps tool, code, partial, and unknown timeline events readable in sequence
   *   order」の条件・入力・操作を実行する。
   * 期待値: tool, code, partial, が維持され、unknown timeline events readable in sequence orderこと。
   */
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

  /**
   * 概要・目的: 「renders a clean legacy session in the same detail flow without schema-specific UI」を通じて、reader と
   *   fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「renders a clean legacy session in the same detail flow without schema-specific
   *   UI」の条件・入力・操作を実行する。
   * 期待値: a clean legacy session in the same detail flow without schema-specific UI が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「keeps other conversation and activity details readable even when one entry lacks renderable body
   *   content」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「keeps other conversation and activity details readable even when one entry lacks renderable body
   *   content」の条件・入力・操作を実行する。
   * 期待値: other conversation が維持され、activity details readable even when one entry lacks renderable body
   *   contentこと。
   */
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

  /**
   * 概要・目的: 「preserves conversation, activity, degraded, and issue metadata for legacy detail responses
   *   too」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「preserves conversation, activity, degraded, and issue metadata for legacy detail responses
   *   too」の条件・入力・操作を実行する。
   * 期待値: conversation, activity, degraded, が保持され、issue metadata for legacy detail responses tooこと。
   */
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

  /**
   * 概要・目的: 「renders a dedicated not found panel with a link back to the index」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「renders a dedicated not found panel with a link back to the index」の条件・入力・操作を実行する。
   * 期待値: a dedicated not found panel with a link back to the index が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「renders an error panel with a link back to the index」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「renders an error panel with a link back to the index」の条件・入力・操作を実行する。
   * 期待値: an error panel with a link back to the index が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「renders an explicit empty conversation state instead of filling the main area with
   *   activity」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「renders an explicit empty conversation state instead of filling the main area with
   *   activity」の条件・入力・操作を実行する。
   * 期待値: an explicit empty conversation state instead of filling the main area with activity が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「requests raw detail only from the explicit raw action and keeps raw status visible」を通じて、HTTP
   *   レスポンスとエラー契約を検証する。
   * テストケース: 「requests raw detail only from the explicit raw action and keeps raw status
   *   visible」の条件・入力・操作を実行する。
   * 期待値: 「requests raw detail only from the explicit raw action and keeps raw status
   *   visible」で示す状態または振る舞いが成立すること。
   */
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

  /**
   * 概要・目的: 「renders disclosures after the conversation and expands session issues only on demand」を通じて、reader
   *   と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「renders disclosures after the conversation and expands session issues only on
   *   demand」の条件・入力・操作を実行する。
   * 期待値: disclosures after the conversation が表示され、expands session issues only on demandこと。
   */
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

  /**
   * 概要・目的: 「keeps the detail page read-only without edit, delete, send, share, timezone, or dedicated
   *   raw-viewer controls」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「keeps the detail page read-only without edit, delete, send, share, timezone, or dedicated
   *   raw-viewer controls」の条件・入力・操作を実行する。
   * 期待値: the detail page read-only without edit, delete, send, share, timezone, or dedicated raw-viewer
   *   controls が維持されること。
   */
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

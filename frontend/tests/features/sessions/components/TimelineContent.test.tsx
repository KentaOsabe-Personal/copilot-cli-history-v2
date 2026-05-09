import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { SessionTimelineEvent } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import TimelineContent from '../../../../src/features/sessions/components/TimelineContent.tsx'

function buildEvent(overrides: Partial<SessionTimelineEvent> = {}): SessionTimelineEvent {
  return {
    sequence: 1,
    kind: 'message',
    mapping_status: 'complete',
    raw_type: 'assistant_message',
    occurred_at: '2026-04-26T09:00:02Z',
    role: 'assistant',
    content: 'hello\n```ts\nconst answer = 42\n```',
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
    ...overrides,
  }
}

describe('TimelineContent', () => {
  /**
   * 概要・目的: 「renders text, code, and tool hint blocks with distinct labels」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders text, code, and tool hint blocks with distinct labels」の条件・入力・操作を実行する。
   * 期待値: text, code, が表示され、tool hint blocks with distinct labelsこと。
   */
  it('renders text, code, and tool hint blocks with distinct labels', () => {
    render(<TimelineContent stateScopeKey="session-1:event-1" event={buildEvent()} />)

    expect(screen.getByText('functions.bash')).toBeInTheDocument()
    expect(screen.getByText('hello')).toBeInTheDocument()
    expect(screen.getByText('const answer = 42')).toBeInTheDocument()
    expect(screen.getByText('ツール呼び出し')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders detail summaries as separate non-message blocks」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders detail summaries as separate non-message blocks」の条件・入力・操作を実行する。
   * 期待値: detail summaries as separate non-message blocks が画面に表示されること。
   */
  it('renders detail summaries as separate non-message blocks', () => {
    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          kind: 'detail',
          role: null,
          content: null,
          tool_calls: [],
          detail: {
            category: 'tool_execution',
            title: 'tool.execution_start',
            body: 'functions.bash / tool-1',
          },
        })}
      />,
    )

    expect(screen.getByText('詳細イベント')).toBeInTheDocument()
    expect(screen.getByText('tool_execution')).toBeInTheDocument()
    expect(screen.getByText('tool.execution_start')).toBeInTheDocument()
    expect(screen.getByText('functions.bash / tool-1')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「wraps prose and detail body text without relying on page-level
   *   overflow」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「wraps prose and detail body text without relying on page-level overflow」の条件・入力・操作を実行する。
   * 期待値: prose and detail body text without relying on page-level overflow が公開用 envelope に包まれること。
   */
  it('wraps prose and detail body text without relying on page-level overflow', () => {
    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          content:
            'This prose block contains aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapWithinTheTimeline',
          tool_calls: [],
          detail: {
            category: 'tool_execution',
            title: 'tool.execution_start',
            body: 'detail-body-with-aVeryLongTokenWithoutNaturalBreakpointsThatShouldAlsoWrap',
          },
        })}
      />,
    )

    expect(
      screen.getByText(
        'This prose block contains aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapWithinTheTimeline',
      ),
    ).toHaveClass('whitespace-pre-wrap', 'break-words')
    expect(
      screen.getByText('detail-body-with-aVeryLongTokenWithoutNaturalBreakpointsThatShouldAlsoWrap'),
    ).toHaveClass('whitespace-pre-wrap', 'break-words')
  })

  /**
   * 概要・目的: 「collapses long tool arguments by default while keeping tool metadata visible」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「collapses long tool arguments by default while keeping tool metadata visible」の条件・入力・操作を実行する。
   * 期待値: 「collapses long tool arguments by default while keeping tool metadata visible」で示す状態または振る舞いが成立すること。
   */
  it('collapses long tool arguments by default while keeping tool metadata visible', () => {
    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          tool_calls: [
            {
              name: 'skill-context',
              arguments_preview: 'line one\nline two',
              is_truncated: true,
              status: 'partial',
            },
          ],
        })}
      />,
    )

    const toolBlock = screen.getByRole('group', { name: 'tool call skill-context' })

    expect(within(toolBlock).getByText('skill-context')).toBeInTheDocument()
    expect(within(toolBlock).getByText('partial')).toBeInTheDocument()
    expect(within(toolBlock).getByText('truncated')).toBeInTheDocument()
    expect(within(toolBlock).getByRole('button', { name: 'arguments を表示' })).toBeInTheDocument()
    expect(within(toolBlock).queryByText('line one\nline two')).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「reveals collapsed arguments inside the same tool block」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「reveals collapsed arguments inside the same tool block」の条件・入力・操作を実行する。
   * 期待値: 「reveals collapsed arguments inside the same tool block」で示す状態または振る舞いが成立すること。
   */
  it('reveals collapsed arguments inside the same tool block', async () => {
    const user = userEvent.setup()

    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          tool_calls: [
            {
              name: 'functions.bash',
              arguments_preview: 'echo one\necho two',
              is_truncated: false,
              status: 'complete',
            },
          ],
        })}
      />,
    )

    const toolBlock = screen.getByRole('group', { name: 'tool call functions.bash' })
    const toggleButton = within(toolBlock).getByRole('button', { name: 'arguments を表示' })
    const controlledRegionId = toggleButton.getAttribute('aria-controls')

    expect(within(toolBlock).queryByText('echo one\necho two')).not.toBeInTheDocument()
    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')
    expect(controlledRegionId).not.toBeNull()
    expect(document.getElementById(controlledRegionId!)).not.toBeNull()

    await user.click(toggleButton)

    expect(toolBlock).toHaveTextContent(/echo one\s+echo two/)
    expect(within(toolBlock).getByText('functions.bash')).toBeInTheDocument()
    expect(within(toolBlock).getByText('ツール呼び出し')).toBeInTheDocument()
    expect(within(toolBlock).getByRole('button', { name: 'arguments を隠す' })).toHaveAttribute(
      'aria-controls',
      controlledRegionId,
    )
    expect(within(toolBlock).getByRole('button', { name: 'arguments を隠す' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(within(toolBlock).getByText(/echo one\s+echo two/).closest('pre')).toHaveClass(
      'overflow-x-auto',
      'whitespace-pre',
    )
  })

  /**
   * 概要・目的: 「starts short single-line arguments collapsed until the user expands them」を通じて、ユーザー操作と callback
   *   の発火を検証する。
   * テストケース: 「starts short single-line arguments collapsed until the user expands them」の条件・入力・操作を実行する。
   * 期待値: 「starts short single-line arguments collapsed until the user expands them」で示す状態または振る舞いが成立すること。
   */
  it('starts short single-line arguments collapsed until the user expands them', () => {
    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          content: null,
          tool_calls: [
            {
              name: 'functions.bash',
              arguments_preview: '{"command":"pwd"}',
              is_truncated: false,
              status: 'complete',
            },
          ],
        })}
      />,
    )

    const toolBlock = screen.getByRole('group', { name: 'tool call functions.bash' })

    expect(within(toolBlock).getByRole('button', { name: 'arguments を表示' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    expect(toolBlock).not.toHaveTextContent('{"command":"pwd"}')
  })

  /**
   * 概要・目的: 「resets disclosure state when the scope changes to a different session with the same
   *   payload」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「resets disclosure state when the scope changes to a different session with the same
   *   payload」の条件・入力・操作を実行する。
   * 期待値: 「resets disclosure state when the scope changes to a different session with the same
   *   payload」で示す状態または振る舞いが成立すること。
   */
  it('resets disclosure state when the scope changes to a different session with the same payload', async () => {
    const user = userEvent.setup()
    const event = buildEvent({
      content: null,
      tool_calls: [
        {
          name: 'skill-context',
          arguments_preview: 'first session\nexpanded',
          is_truncated: true,
          status: 'partial',
        },
      ],
    })
    const { rerender } = render(
      <TimelineContent stateScopeKey="session-1:event-1" event={event} />,
    )

    const firstToolBlock = screen.getByRole('group', { name: 'tool call skill-context' })

    await user.click(within(firstToolBlock).getByRole('button', { name: 'arguments を表示' }))
    expect(firstToolBlock).toHaveTextContent(/first session\s+expanded/)

    rerender(
      <TimelineContent stateScopeKey="session-2:event-1" event={event} />,
    )

    const secondToolBlock = screen.getByRole('group', { name: 'tool call skill-context' })

    expect(within(secondToolBlock).getByRole('button', { name: 'arguments を表示' })).toBeInTheDocument()
    expect(secondToolBlock).not.toHaveTextContent(/first session\s+expanded/)
  })

  /**
   * 概要・目的: 「does not render an arguments toggle when a tool call has no arguments preview」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「does not render an arguments toggle when a tool call has no arguments preview」の条件・入力・操作を実行する。
   * 期待値: render an arguments toggle when a tool call has no arguments preview しないこと。
   */
  it('does not render an arguments toggle when a tool call has no arguments preview', () => {
    render(
      <TimelineContent
        stateScopeKey="session-1:event-1"
        event={buildEvent({
          content: null,
          tool_calls: [
            {
              name: 'functions.read',
              arguments_preview: null,
              is_truncated: false,
              status: 'complete',
            },
          ],
        })}
      />,
    )

    const toolBlock = screen.getByRole('group', { name: 'tool call functions.read' })

    expect(within(toolBlock).getByText('functions.read')).toBeInTheDocument()
    expect(within(toolBlock).queryByRole('button')).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps code blocks in block-local horizontal scroll containers」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps code blocks in block-local horizontal scroll containers」の条件・入力・操作を実行する。
   * 期待値: code blocks in block-local horizontal scroll containers が維持されること。
   */
  it('keeps code blocks in block-local horizontal scroll containers', () => {
    render(<TimelineContent stateScopeKey="session-1:event-1" event={buildEvent()} />)

    expect(screen.getByText('const answer = 42').closest('pre')).toHaveClass(
      'overflow-x-auto',
      'whitespace-pre',
    )
  })
})

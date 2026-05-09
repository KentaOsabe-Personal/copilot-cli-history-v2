import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { SessionConversation } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import ConversationTranscript from '../../../../src/features/sessions/components/ConversationTranscript.tsx'

function buildConversation(): SessionConversation {
  return {
    message_count: 2,
    empty_reason: null,
    summary: {
      has_conversation: true,
      message_count: 2,
      preview: 'Need help',
      activity_count: 0,
    },
    entries: [
      {
        sequence: 1,
        role: 'user',
        content: 'Need help with the CLI output',
        occurred_at: '2026-04-26T09:00:00Z',
        tool_calls: [],
        degraded: false,
        issues: [],
      },
      {
        sequence: 2,
        role: 'assistant',
        content: 'Here is the cleaned-up summary',
        occurred_at: '2026-04-26T09:01:00Z',
        tool_calls: [],
        degraded: true,
        issues: [
          {
            code: 'partial_message',
            severity: 'warning',
            message: 'message was incomplete',
            source_path: null,
            scope: 'event',
            event_sequence: 2,
          },
        ],
      },
    ],
  }
}

describe('ConversationTranscript', () => {
  /**
   * 概要・目的: 「marks user and assistant entries with role-specific visual state beyond the role badge」を通じて、hook
   *   の状態遷移と非同期制御を検証する。
   * テストケース: 「marks user and assistant entries with role-specific visual state beyond the role
   *   badge」の条件・入力・操作を実行する。
   * 期待値: 「marks user and assistant entries with role-specific visual state beyond the role
   *   badge」で示す状態または振る舞いが成立すること。
   */
  it('marks user and assistant entries with role-specific visual state beyond the role badge', () => {
    render(<ConversationTranscript conversation={buildConversation()} stateScopeKey="session-1" />)

    expect(screen.getByTestId('conversation-entry-1')).toHaveAttribute('data-role', 'user')
    expect(screen.getByTestId('conversation-entry-1')).toHaveClass('border-emerald-300/35')
    expect(screen.getByTestId('conversation-entry-2')).toHaveAttribute('data-role', 'assistant')
    expect(screen.getByTestId('conversation-entry-2')).toHaveClass('border-cyan-300/35')
  })

  /**
   * 概要・目的: 「keeps degraded and issue indicators readable with assistant role styling」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps degraded and issue indicators readable with assistant role styling」の条件・入力・操作を実行する。
   * 期待値: degraded が維持され、issue indicators readable with assistant role stylingこと。
   */
  it('keeps degraded and issue indicators readable with assistant role styling', () => {
    render(<ConversationTranscript conversation={buildConversation()} stateScopeKey="session-1" />)

    const assistantEntry = screen.getByTestId('conversation-entry-2')

    expect(assistantEntry).toHaveAttribute('data-role', 'assistant')
    expect(assistantEntry).toHaveTextContent('partial')
    expect(assistantEntry).toHaveTextContent('message was incomplete')
  })

  /**
   * 概要・目的: 「hides and restores entry body, code, tool hints, and issue details while keeping metadata
   *   visible」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「hides and restores entry body, code, tool hints, and issue details while keeping metadata
   *   visible」の条件・入力・操作を実行する。
   * 期待値: 「hides and restores entry body, code, tool hints, and issue details while keeping metadata
   *   visible」で示す状態または振る舞いが成立すること。
   */
  it('hides and restores entry body, code, tool hints, and issue details while keeping metadata visible', async () => {
    const user = userEvent.setup()
    const conversation: SessionConversation = {
      ...buildConversation(),
      entries: [
        {
          sequence: 7,
          role: 'assistant',
          content: 'Visible body\n```sh\nnpm test\n```',
          occurred_at: '2026-04-26T09:01:00Z',
          tool_calls: [
            {
              name: 'skill-context',
              arguments_preview: 'long\ncontext',
              is_truncated: true,
              status: 'partial',
            },
          ],
          degraded: true,
          issues: [
            {
              code: 'partial_message',
              severity: 'warning',
              message: 'message was incomplete',
              source_path: null,
              scope: 'event',
              event_sequence: 7,
            },
          ],
        },
      ],
    }

    render(<ConversationTranscript conversation={conversation} stateScopeKey="session-1" />)

    const entry = screen.getByTestId('conversation-entry-7')
    const toggleButton = screen.getByRole('button', { name: '発話 #7 を非表示' })
    const controlledRegionId = toggleButton.getAttribute('aria-controls')

    expect(entry).toHaveTextContent('Visible body')
    expect(entry).toHaveTextContent('npm test')
    expect(entry).toHaveTextContent('skill-context')
    expect(entry).toHaveTextContent('message was incomplete')
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true')
    expect(controlledRegionId).not.toBeNull()
    expect(document.getElementById(controlledRegionId!)).not.toBeNull()

    await user.click(toggleButton)

    expect(entry).toHaveTextContent('発話 #7')
    expect(entry).toHaveTextContent('assistant')
    expect(entry).toHaveTextContent('2026-04-26 18:01:00 JST')
    expect(entry).toHaveTextContent('partial')
    expect(screen.getByRole('button', { name: '発話 #7 を表示' })).toHaveAttribute('aria-controls', controlledRegionId)
    expect(screen.getByRole('button', { name: '発話 #7 を表示' })).toHaveAttribute('aria-expanded', 'false')
    expect(entry).not.toHaveTextContent('Visible body')
    expect(entry).not.toHaveTextContent('npm test')
    expect(entry).not.toHaveTextContent('skill-context')
    expect(entry).not.toHaveTextContent('message was incomplete')

    await user.click(screen.getByRole('button', { name: '発話 #7 を表示' }))

    expect(entry).toHaveTextContent('Visible body')
    expect(entry).toHaveTextContent('npm test')
    expect(entry).toHaveTextContent('skill-context')
    expect(entry).toHaveTextContent('message was incomplete')
    expect(screen.getByRole('button', { name: '発話 #7 を非表示' })).toHaveAttribute('aria-controls', controlledRegionId)
    expect(screen.getByRole('button', { name: '発話 #7 を非表示' })).toHaveAttribute('aria-expanded', 'true')
  })

  /**
   * 概要・目的: 「does not add an empty-body placeholder when a tool-only entry is expanded」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「does not add an empty-body placeholder when a tool-only entry is expanded」の条件・入力・操作を実行する。
   * 期待値: add an empty-body placeholder when a tool-only entry is expanded しないこと。
   */
  it('does not add an empty-body placeholder when a tool-only entry is expanded', async () => {
    const user = userEvent.setup()
    const conversation: SessionConversation = {
      ...buildConversation(),
      entries: [
        {
          sequence: 9,
          role: 'assistant',
          content: '',
          occurred_at: '2026-04-26T09:02:00Z',
          tool_calls: [
            {
              name: 'skill-context',
              arguments_preview: 'long\ncontext',
              is_truncated: true,
              status: 'partial',
            },
          ],
          degraded: false,
          issues: [
            {
              code: 'tool.partial',
              severity: 'warning',
              message: 'tool context was truncated',
              source_path: null,
              scope: 'event',
              event_sequence: 9,
            },
          ],
        },
      ],
      message_count: 1,
    }

    render(<ConversationTranscript conversation={conversation} stateScopeKey="session-1" />)

    const entry = screen.getByTestId('conversation-entry-9')

    await user.click(screen.getByRole('button', { name: '発話 #9 を表示' }))

    expect(entry).toHaveTextContent('skill-context')
    expect(entry).toHaveTextContent('tool context was truncated')
    expect(entry).not.toHaveTextContent('表示できる会話本文はありません')
  })

  /**
   * 概要・目的: 「starts tool-only entries hidden by default and reveals them after expanding」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「starts tool-only entries hidden by default and reveals them after expanding」の条件・入力・操作を実行する。
   * 期待値: 「starts tool-only entries hidden by default and reveals them after expanding」で示す状態または振る舞いが成立すること。
   */
  it('starts tool-only entries hidden by default and reveals them after expanding', async () => {
    const user = userEvent.setup()
    const conversation: SessionConversation = {
      ...buildConversation(),
      entries: [
        {
          sequence: 10,
          role: 'assistant',
          content: '',
          occurred_at: '2026-04-26T09:02:30Z',
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
    }

    render(<ConversationTranscript conversation={conversation} stateScopeKey="session-1" />)

    const entry = screen.getByTestId('conversation-entry-10')
    const toggleButton = screen.getByRole('button', { name: '発話 #10 を表示' })

    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')
    expect(entry).toHaveTextContent('発話 #10')
    expect(entry).not.toHaveTextContent('functions.bash')
    expect(entry).not.toHaveTextContent('{"command":"pwd"}')

    await user.click(toggleButton)

    expect(screen.getByRole('button', { name: '発話 #10 を非表示' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(entry).toHaveTextContent('functions.bash')
  })

  /**
   * 概要・目的: 「starts entries that begin with a skill-context tag hidden by default」を通じて、ユーザー操作と callback
   *   の発火を検証する。
   * テストケース: 「starts entries that begin with a skill-context tag hidden by default」の条件・入力・操作を実行する。
   * 期待値: 「starts entries that begin with a skill-context tag hidden by default」で示す状態または振る舞いが成立すること。
   */
  it('starts entries that begin with a skill-context tag hidden by default', async () => {
    const user = userEvent.setup()
    const conversation: SessionConversation = {
      ...buildConversation(),
      entries: [
        {
          sequence: 11,
          role: 'assistant',
          content:
            '<skill-context name="kiro-debug">\nlong hidden context\n</skill-context>\nVisible after expand',
          occurred_at: '2026-04-26T09:03:00Z',
          tool_calls: [],
          degraded: false,
          issues: [],
        },
      ],
      message_count: 1,
    }

    render(<ConversationTranscript conversation={conversation} stateScopeKey="session-1" />)

    const entry = screen.getByTestId('conversation-entry-11')
    const toggleButton = screen.getByRole('button', { name: '発話 #11 を表示' })

    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')
    expect(entry).toHaveTextContent('発話 #11')
    expect(entry).toHaveTextContent('assistant')
    expect(entry).not.toHaveTextContent('long hidden context')
    expect(entry).not.toHaveTextContent('Visible after expand')

    await user.click(toggleButton)

    expect(screen.getByRole('button', { name: '発話 #11 を非表示' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    expect(entry).toHaveTextContent('long hidden context')
    expect(entry).toHaveTextContent('Visible after expand')
  })

  /**
   * 概要・目的: 「resets entry visibility when the scope changes to a different session with the same
   *   payload」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「resets entry visibility when the scope changes to a different session with the same
   *   payload」の条件・入力・操作を実行する。
   * 期待値: 「resets entry visibility when the scope changes to a different session with the same
   *   payload」で示す状態または振る舞いが成立すること。
   */
  it('resets entry visibility when the scope changes to a different session with the same payload', async () => {
    const user = userEvent.setup()
    const conversation = buildConversation()
    const { rerender } = render(
      <ConversationTranscript conversation={conversation} stateScopeKey="session-1" />,
    )

    await user.click(screen.getByRole('button', { name: '発話 #1 を非表示' }))

    expect(screen.queryByText('Need help with the CLI output')).not.toBeInTheDocument()

    rerender(
      <ConversationTranscript conversation={conversation} stateScopeKey="session-2" />,
    )

    expect(screen.getByText('Need help with the CLI output')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '発話 #1 を非表示' })).toBeInTheDocument()
  })
})

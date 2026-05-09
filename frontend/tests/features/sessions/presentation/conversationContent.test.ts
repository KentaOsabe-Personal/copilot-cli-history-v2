import { describe, expect, it } from 'vitest'

import type { SessionConversationEntry } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import {
  shouldDefaultHideConversationEntry,
  formatConversationEntryContent,
  shouldDefaultHideConversationEntryContent,
} from '../../../../src/features/sessions/presentation/conversationContent.ts'

function buildEntry(overrides: Partial<SessionConversationEntry> = {}): SessionConversationEntry {
  return {
    sequence: 1,
    role: 'assistant',
    content: 'Before code\n```ts\nconst answer = 42\n```\nAfter code',
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
    ...overrides,
  }
}

describe('formatConversationEntryContent', () => {
  /**
   * 概要・目的: 「preserves text/code order and keeps tool hints as separate attached
   *   blocks」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「preserves text/code order and keeps tool hints as separate attached blocks」の条件・入力・操作を実行する。
   * 期待値: text/code order が保持され、tool hints as separate attached blocks が維持されること。
   */
  it('preserves text/code order and keeps tool hints as separate attached blocks', () => {
    expect(formatConversationEntryContent(buildEntry())).toEqual({
      role: 'assistant',
      sequence: 1,
      occurredAt: '2026-04-26T09:00:02Z',
      degraded: false,
      issues: [],
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
   * 概要・目的: 「keeps partial tool hints readable even when the assistant content is empty」を通じて、reader と fixture
   *   の読取・劣化時の扱いを検証する。
   * テストケース: 「keeps partial tool hints readable even when the assistant content is empty」の条件・入力・操作を実行する。
   * 期待値: partial tool hints readable even when the assistant content is empty が維持されること。
   */
  it('keeps partial tool hints readable even when the assistant content is empty', () => {
    expect(
      formatConversationEntryContent(
        buildEntry({
          content: '',
          tool_calls: [
            {
              name: null,
              arguments_preview: null,
              is_truncated: true,
              status: 'partial',
            },
          ],
        }),
      ),
    ).toMatchObject({
      blocks: [
        {
          kind: 'tool_hint',
          name: null,
          argumentsPreview: null,
          isTruncated: true,
          status: 'partial',
          argumentsDefaultCollapsed: true,
          collapseReason: 'truncated_arguments',
        },
      ],
    })
  })

  /**
   * 概要・目的: 「collapses skill-context tool arguments by default without dropping tool metadata」を通じて、検索・日付条件と
   *   query 組み立てを検証する。
   * テストケース: 「collapses skill-context tool arguments by default without dropping tool metadata」の条件・入力・操作を実行する。
   * 期待値: 「collapses skill-context tool arguments by default without dropping tool
   *   metadata」で示す状態または振る舞いが成立すること。
   */
  it('collapses skill-context tool arguments by default without dropping tool metadata', () => {
    expect(
      formatConversationEntryContent(
        buildEntry({
          tool_calls: [
            {
              name: 'skill-context',
              arguments_preview: '{"skill":"kiro-impl"}',
              is_truncated: false,
              status: 'complete',
            },
          ],
        }),
      ),
    ).toMatchObject({
      blocks: [
        expect.any(Object),
        expect.any(Object),
        expect.any(Object),
        {
          kind: 'tool_hint',
          name: 'skill-context',
          argumentsPreview: '{"skill":"kiro-impl"}',
          isTruncated: false,
          status: 'complete',
          argumentsDefaultCollapsed: true,
          collapseReason: 'skill_context',
        },
      ],
    })
  })

  /**
   * 概要・目的: 「collapses every tool arguments preview by default while preserving the collapse
   *   reason」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「collapses every tool arguments preview by default while preserving the collapse
   *   reason」の条件・入力・操作を実行する。
   * 期待値: 「collapses every tool arguments preview by default while preserving the collapse
   *   reason」で示す状態または振る舞いが成立すること。
   */
  it('collapses every tool arguments preview by default while preserving the collapse reason', () => {
    expect(
      formatConversationEntryContent(
        buildEntry({
          content: '',
          tool_calls: [
            {
              name: 'functions.exec_command',
              arguments_preview: 'line 1\nline 2',
              is_truncated: false,
              status: 'complete',
            },
            {
              name: 'functions.exec_command',
              arguments_preview: '{"command":"long"}',
              is_truncated: true,
              status: 'partial',
            },
            {
              name: 'functions.exec_command',
              arguments_preview: '{"command":"pwd"}',
              is_truncated: false,
              status: 'complete',
            },
            {
              name: 'functions.exec_command',
              arguments_preview: null,
              is_truncated: false,
              status: 'complete',
            },
          ],
        }),
      ).blocks,
    ).toEqual([
      {
        kind: 'tool_hint',
        name: 'functions.exec_command',
        argumentsPreview: 'line 1\nline 2',
        isTruncated: false,
        status: 'complete',
        argumentsDefaultCollapsed: true,
        collapseReason: 'multiline_arguments',
      },
      {
        kind: 'tool_hint',
        name: 'functions.exec_command',
        argumentsPreview: '{"command":"long"}',
        isTruncated: true,
        status: 'partial',
        argumentsDefaultCollapsed: true,
        collapseReason: 'truncated_arguments',
      },
      {
        kind: 'tool_hint',
        name: 'functions.exec_command',
        argumentsPreview: '{"command":"pwd"}',
        isTruncated: false,
        status: 'complete',
        argumentsDefaultCollapsed: true,
        collapseReason: 'arguments_preview',
      },
      {
        kind: 'tool_hint',
        name: 'functions.exec_command',
        argumentsPreview: null,
        isTruncated: false,
        status: 'complete',
        argumentsDefaultCollapsed: false,
        collapseReason: 'none',
      },
    ])
  })
})

describe('shouldDefaultHideConversationEntryContent', () => {
  /**
   * 概要・目的: 「returns true when the entry starts with a skill-context tag」を通じて、ユーザー操作と callback の発火を検証する。
   * テストケース: 「returns true when the entry starts with a skill-context tag」の条件・入力・操作を実行する。
   * 期待値: true when the entry starts with a skill-context tag を返すこと。
   */
  it('returns true when the entry starts with a skill-context tag', () => {
    expect(
      shouldDefaultHideConversationEntryContent(
        '  <skill-context name="kiro-debug">\ncontext body\n</skill-context>',
      ),
    ).toBe(true)
  })

  /**
   * 概要・目的: 「returns false for regular message content and tool-only entries」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「returns false for regular message content and tool-only entries」の条件・入力・操作を実行する。
   * 期待値: false for regular message content and tool-only entries を返すこと。
   */
  it('returns false for regular message content and tool-only entries', () => {
    expect(shouldDefaultHideConversationEntryContent('I will inspect the current session.')).toBe(
      false,
    )
    expect(shouldDefaultHideConversationEntryContent('')).toBe(false)
    expect(shouldDefaultHideConversationEntryContent(null)).toBe(false)
  })
})

describe('shouldDefaultHideConversationEntry', () => {
  /**
   * 概要・目的: 「returns true when the entry has only tool calls and no visible body content」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「returns true when the entry has only tool calls and no visible body content」の条件・入力・操作を実行する。
   * 期待値: true when the entry has only tool calls and no visible body content を返すこと。
   */
  it('returns true when the entry has only tool calls and no visible body content', () => {
    expect(
      shouldDefaultHideConversationEntry(
        buildEntry({
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
      ),
    ).toBe(true)
  })

  /**
   * 概要・目的: 「returns true when the entry body is whitespace only and tool calls are
   *   present」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「returns true when the entry body is whitespace only and tool calls are present」の条件・入力・操作を実行する。
   * 期待値: true when the entry body is whitespace only and tool calls are present を返すこと。
   */
  it('returns true when the entry body is whitespace only and tool calls are present', () => {
    expect(
      shouldDefaultHideConversationEntry(
        buildEntry({
          content: '  \n\t  ',
          tool_calls: [
            {
              name: 'functions.bash',
              arguments_preview: '{"command":"pwd"}',
              is_truncated: false,
              status: 'complete',
            },
          ],
        }),
      ),
    ).toBe(true)
  })

  /**
   * 概要・目的: 「returns false when the entry still has visible prose alongside tool calls」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「returns false when the entry still has visible prose alongside tool calls」の条件・入力・操作を実行する。
   * 期待値: false when the entry still has visible prose alongside tool calls を返すこと。
   */
  it('returns false when the entry still has visible prose alongside tool calls', () => {
    expect(
      shouldDefaultHideConversationEntry(
        buildEntry({
          content: 'I will inspect the current session.',
          tool_calls: [
            {
              name: 'functions.bash',
              arguments_preview: '{"command":"pwd"}',
              is_truncated: false,
              status: 'complete',
            },
          ],
        }),
      ),
    ).toBe(false)
  })
})

import { describe, expect, it } from 'vitest'

import type { SessionConversationEntry } from '../api/sessionApi.types.ts'
import {
  shouldDefaultHideConversationEntry,
  formatConversationEntryContent,
  shouldDefaultHideConversationEntryContent,
} from './conversationContent.ts'

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
  it('returns true when the entry starts with a skill-context tag', () => {
    expect(
      shouldDefaultHideConversationEntryContent(
        '  <skill-context name="kiro-debug">\ncontext body\n</skill-context>',
      ),
    ).toBe(true)
  })

  it('returns false for regular message content and tool-only entries', () => {
    expect(shouldDefaultHideConversationEntryContent('I will inspect the current session.')).toBe(
      false,
    )
    expect(shouldDefaultHideConversationEntryContent('')).toBe(false)
    expect(shouldDefaultHideConversationEntryContent(null)).toBe(false)
  })
})

describe('shouldDefaultHideConversationEntry', () => {
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

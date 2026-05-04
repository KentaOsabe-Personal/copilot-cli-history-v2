import type {
  SessionConversationEntry,
  SessionIssue,
  SessionTimelineToolCall,
} from '../api/sessionApi.types.ts'

export type ConversationVisualBlock =
  | { kind: 'text'; text: string }
  | { kind: 'code'; language: string | null; code: string }
  | {
      kind: 'tool_hint'
      name: string | null
      argumentsPreview: string | null
      isTruncated: boolean
      status: 'complete' | 'partial'
      argumentsDefaultCollapsed: boolean
      collapseReason: ToolCollapseReason
    }

export type ToolCollapseReason =
  | 'skill_context'
  | 'multiline_arguments'
  | 'truncated_arguments'
  | 'arguments_preview'
  | 'none'

export interface ConversationEntryContentModel {
  role: 'user' | 'assistant'
  sequence: number
  occurredAt: string | null
  degraded: boolean
  issues: readonly SessionIssue[]
  blocks: readonly ConversationVisualBlock[]
}

const CODE_FENCE_PATTERN = /```([^\n`]*)\n?([\s\S]*?)```/g
const SKILL_CONTEXT_PREFIX = '<skill-context'

export function formatConversationEntryContent(
  entry: SessionConversationEntry,
): ConversationEntryContentModel {
  return {
    role: entry.role,
    sequence: entry.sequence,
    occurredAt: entry.occurred_at,
    degraded: entry.degraded,
    issues: entry.issues,
    blocks: [
      ...extractContentBlocks(entry.content),
      ...extractToolHintBlocks(entry.tool_calls),
    ],
  }
}

export function extractContentBlocks(content: string | null): ConversationVisualBlock[] {
  if (content == null || content.length === 0) {
    return []
  }

  const blocks: ConversationVisualBlock[] = []
  let lastIndex = 0

  for (const match of content.matchAll(CODE_FENCE_PATTERN)) {
    const [fullMatch, languageHint, code] = match
    const matchIndex = match.index ?? 0

    pushTextBlock(blocks, content.slice(lastIndex, matchIndex))
    blocks.push({
      kind: 'code',
      language: normalizeLanguage(languageHint),
      code,
    })
    lastIndex = matchIndex + fullMatch.length
  }

  pushTextBlock(blocks, content.slice(lastIndex))

  return blocks
}

export function extractToolHintBlocks(
  toolCalls: readonly SessionTimelineToolCall[] | undefined,
): ConversationVisualBlock[] {
  return (toolCalls ?? []).map((toolCall) => {
    const collapseReason = resolveToolCollapseReason(toolCall)

    return {
      kind: 'tool_hint',
      name: toolCall.name,
      argumentsPreview: toolCall.arguments_preview,
      isTruncated: toolCall.is_truncated,
      status: toolCall.status,
      argumentsDefaultCollapsed: collapseReason !== 'none',
      collapseReason,
    }
  })
}

export function shouldDefaultHideConversationEntryContent(content: string | null): boolean {
  if (content == null) {
    return false
  }

  return content.trimStart().startsWith(SKILL_CONTEXT_PREFIX)
}

export function shouldDefaultHideConversationEntry(
  entry: Pick<SessionConversationEntry, 'content' | 'tool_calls'>,
): boolean {
  return shouldDefaultHideByBlocks([
    ...extractContentBlocks(entry.content),
    ...extractToolHintBlocks(entry.tool_calls),
  ])
}

export function shouldDefaultHideConversationEntryModel(
  model: ConversationEntryContentModel,
): boolean {
  return shouldDefaultHideByBlocks(model.blocks)
}

function shouldDefaultHideByBlocks(blocks: readonly ConversationVisualBlock[]): boolean {
  const firstBlock = blocks[0]
  if (firstBlock?.kind === 'text' && firstBlock.text.trimStart().startsWith(SKILL_CONTEXT_PREFIX)) {
    return true
  }

  if (!blocks.some((b) => b.kind === 'tool_hint')) {
    return false
  }

  return !blocks.some((b) => {
    if (b.kind === 'code') {
      return true
    }

    if (b.kind !== 'text') {
      return false
    }

    return b.text.trim().length > 0
  })
}

function resolveToolCollapseReason(toolCall: SessionTimelineToolCall): ToolCollapseReason {
  if (toolCall.name === 'skill-context') {
    return 'skill_context'
  }

  if (toolCall.is_truncated) {
    return 'truncated_arguments'
  }

  if (toolCall.arguments_preview == null) {
    return 'none'
  }

  if (toolCall.arguments_preview?.includes('\n') === true) {
    return 'multiline_arguments'
  }

  return 'arguments_preview'
}

function pushTextBlock(blocks: ConversationVisualBlock[], text: string) {
  if (text.length === 0) {
    return
  }

  blocks.push({
    kind: 'text',
    text,
  })
}

function normalizeLanguage(value: string): string | null {
  const language = value.trim()

  return language.length > 0 ? language : null
}

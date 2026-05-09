import { describe, expect, it } from 'vitest'

import {
  sessionUiDetailScenarios,
  sessionUiSummaryScenarios,
} from './sessionUiTestData.ts'

function hasDisplayableWorkContext(workContext: {
  cwd: string | null
  git_root: string | null
  repository: string | null
  branch: string | null
}) {
  return Object.values(workContext).some((value) => typeof value === 'string' && value.trim().length > 0)
}

describe('sessionUiTestData', () => {
  it('provides list scenarios for present metadata, missing metadata, metadata-only, workspace-only, and degraded sessions', () => {
    expect(sessionUiSummaryScenarios.withWorkContextAndModel).toMatchObject({
      source_format: 'current',
      selected_model: 'gpt-5-current',
      source_state: 'complete',
      degraded: false,
      conversation_summary: {
        has_conversation: true,
      },
    })
    expect(hasDisplayableWorkContext(sessionUiSummaryScenarios.withWorkContextAndModel.work_context)).toBe(true)

    expect(sessionUiSummaryScenarios.missingWorkContextAndModel).toMatchObject({
      source_format: 'legacy',
      selected_model: null,
      source_state: 'complete',
      degraded: false,
      conversation_summary: {
        has_conversation: true,
      },
    })
    expect(hasDisplayableWorkContext(sessionUiSummaryScenarios.missingWorkContextAndModel.work_context)).toBe(false)

    expect(sessionUiSummaryScenarios.metadataOnly).toMatchObject({
      source_state: 'complete',
      degraded: false,
      conversation_summary: {
        has_conversation: false,
        message_count: 0,
        preview: null,
      },
    })
    expect(sessionUiSummaryScenarios.workspaceOnly).toMatchObject({
      source_state: 'workspace_only',
      conversation_summary: {
        has_conversation: false,
      },
    })
    expect(sessionUiSummaryScenarios.degraded).toMatchObject({
      source_state: 'degraded',
      degraded: true,
    })
    expect(sessionUiSummaryScenarios.degraded.issues).toHaveLength(1)
  })

  it('keeps model display assertions based on actual data presence instead of storage format', () => {
    expect(sessionUiSummaryScenarios.withWorkContextAndModel.source_format).toBe('current')
    expect(sessionUiSummaryScenarios.legacyWithModel.source_format).toBe('legacy')
    expect(sessionUiSummaryScenarios.withWorkContextAndModel.selected_model).toBeTruthy()
    expect(sessionUiSummaryScenarios.legacyWithModel.selected_model).toBeTruthy()
    expect(sessionUiSummaryScenarios.currentWithoutModel.source_format).toBe('current')
    expect(sessionUiSummaryScenarios.legacyWithoutModel.source_format).toBe('legacy')
    expect(sessionUiSummaryScenarios.currentWithoutModel.selected_model).toBeNull()
    expect(sessionUiSummaryScenarios.legacyWithoutModel.selected_model).toBeNull()
  })

  it('provides detail scenarios that isolate session issues, utterance issues, tool calls, skill-context, and activity', () => {
    const detail = sessionUiDetailScenarios.interactionSurface

    expect(detail.issues).toEqual([
      expect.objectContaining({
        scope: 'session',
        event_sequence: null,
        message: 'session timeline is incomplete',
      }),
    ])

    const utteranceWithIssue = detail.conversation.entries.find((entry) =>
      entry.issues.some((issue) => issue.event_sequence === entry.sequence),
    )
    expect(utteranceWithIssue).toMatchObject({
      role: 'assistant',
      degraded: true,
    })
    expect(utteranceWithIssue?.issues[0]).toMatchObject({
      scope: 'event',
      message: 'assistant response was partially mapped',
    })

    expect(
      detail.conversation.entries.some((entry) =>
        entry.tool_calls.some((toolCall) => toolCall.name === 'functions.bash'),
      ),
    ).toBe(true)
    expect(
      detail.conversation.entries.some((entry) =>
        entry.tool_calls.some((toolCall) => toolCall.name === 'skill-context'),
      ),
    ).toBe(true)
    expect(detail.activity.entries).toEqual([
      expect.objectContaining({
        title: 'tool.execution_start',
        degraded: true,
        issues: [expect.objectContaining({ message: 'activity payload is partial' })],
      }),
      expect.objectContaining({
        title: 'session.checkpoint',
        degraded: false,
        issues: [],
      }),
    ])
  })

  it('provides detail scenarios for metadata-only and workspace-only empty conversation states', () => {
    expect(sessionUiDetailScenarios.metadataOnly).toMatchObject({
      source_state: 'complete',
      conversation: {
        entries: [],
        empty_reason: 'no_conversation_messages',
      },
      activity: {
        entries: [],
      },
    })
    expect(sessionUiDetailScenarios.workspaceOnly).toMatchObject({
      source_state: 'workspace_only',
      conversation: {
        entries: [],
        empty_reason: 'events_unavailable',
      },
    })
  })
})

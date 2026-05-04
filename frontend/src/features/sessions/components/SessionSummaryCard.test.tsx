import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import {
  buildSessionUiSummary,
  sessionUiSummaryScenarios,
} from '../testing/sessionUiTestData.ts'
import SessionSummaryCard from './SessionSummaryCard.tsx'

describe('SessionSummaryCard', () => {
  it('keeps ordinary sessions focused on preview, message count, and real metadata only', () => {
    render(
      <MemoryRouter>
        <SessionSummaryCard session={sessionUiSummaryScenarios.withWorkContextAndModel} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Review the session UI fixtures')).toBeInTheDocument()
    expect(screen.getByText('2 件の会話')).toBeInTheDocument()
    expect(screen.getByText('octo/copilot-cli-history @ main')).toBeInTheDocument()
    expect(screen.getByText('gpt-5-current')).toBeInTheDocument()
    expect(screen.queryByText('会話あり')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
    expect(screen.queryByText('complete')).not.toBeInTheDocument()
    expect(screen.queryByText('1 件の内部 activity')).not.toBeInTheDocument()
  })

  it('shows metadata-only as an exception signal when a complete session has no conversation', () => {
    render(
      <MemoryRouter>
        <SessionSummaryCard
          session={buildSessionUiSummary({
            ...sessionUiSummaryScenarios.metadataOnly,
            id: 'metadata-only-session',
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('metadata-only')).toBeInTheDocument()
    expect(screen.queryByText('会話あり')).not.toBeInTheDocument()
    expect(screen.queryByText('complete')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
  })

  it('shows only exceptional source-state and degradation signals', () => {
    const { rerender } = render(
      <MemoryRouter>
        <SessionSummaryCard
          session={buildSessionUiSummary({
            ...sessionUiSummaryScenarios.workspaceOnly,
            id: 'workspace-only-session',
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('workspace-only')).toBeInTheDocument()
    expect(screen.queryByText('metadata-only')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <SessionSummaryCard
          session={buildSessionUiSummary({
            id: 'degraded-complete-session',
            source_state: 'degraded',
            degraded: true,
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('一部欠損あり')).toBeInTheDocument()
    expect(screen.queryByText('degraded')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
  })

  it('falls back to created_at and applies wrap-safe classes for long values', () => {
    render(
      <MemoryRouter>
        <SessionSummaryCard
          session={buildSessionUiSummary({
            id: 'session-with-an-extremely-long-identifier-that-should-break-without-expanding-the-page-width',
            updated_at: null,
            created_at: '2026-04-26T09:00:00Z',
            work_context: {
              cwd: '/workspace/very-long-path-segment/that/keeps/going/without/natural/breakpoints',
              git_root:
                '/workspace/very-long-path-segment/that/keeps/going/without/natural/breakpoints',
              repository:
                'octo/copilot-cli-history-with-a-very-long-repository-name-that-needs-to-wrap',
              branch:
                'feature/overflow-safe-rendering-for-session-summary-cards-with-long-identifiers',
            },
            conversation_summary: {
              has_conversation: true,
              message_count: 1,
              preview:
                'This preview includes aSuperLongTokenWithoutNaturalBreakpointsThatShouldStillWrapInsideTheCard',
              activity_count: 0,
            },
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('2026-04-26 18:00:00 JST')).toBeInTheDocument()
    expect(screen.getByText('表示日時')).toBeInTheDocument()
    expect(
      screen.getByText(
        'session-with-an-extremely-long-identifier-that-should-break-without-expanding-the-page-width',
      ),
    ).toHaveClass('break-all')
    expect(
      screen.getByText(
        'This preview includes aSuperLongTokenWithoutNaturalBreakpointsThatShouldStillWrapInsideTheCard',
      ),
    ).toHaveClass('whitespace-pre-wrap', 'break-words')
    expect(
      screen.getByText(
        'octo/copilot-cli-history-with-a-very-long-repository-name-that-needs-to-wrap @ feature/overflow-safe-rendering-for-session-summary-cards-with-long-identifiers',
      ),
    ).toHaveClass('break-words')
  })
})

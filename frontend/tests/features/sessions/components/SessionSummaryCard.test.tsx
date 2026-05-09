import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import {
  buildSessionUiSummary,
  sessionUiSummaryScenarios,
} from '../testing/sessionUiTestData.ts'
import SessionSummaryCard from '../../../../src/features/sessions/components/SessionSummaryCard.tsx'

describe('SessionSummaryCard', () => {
  /**
   * 概要・目的: 「keeps ordinary sessions focused on preview, message count, and real metadata
   *   only」を通じて、否定条件・例外条件の分岐を検証する。
   * テストケース: 「keeps ordinary sessions focused on preview, message count, and real metadata
   *   only」の条件・入力・操作を実行する。
   * 期待値: ordinary sessions focused on preview, message count, が維持され、real metadata onlyこと。
   */
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

  /**
   * 概要・目的: 「shows metadata-only as an exception signal when a complete session has no
   *   conversation」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「shows metadata-only as an exception signal when a complete session has no
   *   conversation」の条件・入力・操作を実行する。
   * 期待値: metadata-only as an exception signal when a complete session has no conversation が表示されること。
   */
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

  /**
   * 概要・目的: 「shows only exceptional source-state signals on the summary card」を通じて、reader と fixture
   *   の読取・劣化時の扱いを検証する。
   * テストケース: 「shows only exceptional source-state signals on the summary card」の条件・入力・操作を実行する。
   * 期待値: only exceptional source-state signals on the summary card が表示されること。
   */
  it('shows only exceptional source-state signals on the summary card', () => {
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

    expect(screen.queryByText('一部欠損あり')).not.toBeInTheDocument()
    expect(screen.queryByText('degraded')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「falls back to created_at and applies wrap-safe classes for long values」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「falls back to created_at and applies wrap-safe classes for long values」の条件・入力・操作を実行する。
   * 期待値: created_at and applies wrap-safe classes for long values に fallback すること。
   */
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

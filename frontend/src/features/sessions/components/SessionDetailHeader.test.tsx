import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import {
  buildSessionUiDetail,
  sessionUiDetailScenarios,
} from '../testing/sessionUiTestData.ts'
import SessionDetailHeader from './SessionDetailHeader.tsx'

describe('SessionDetailHeader', () => {
  it('shows only real metadata values for an ordinary complete session', () => {
    render(
      <MemoryRouter>
        <SessionDetailHeader
          detail={buildSessionUiDetail({
            id: 'detail-complete',
            source_state: 'complete',
            degraded: false,
            issues: [],
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('octo/copilot-cli-history @ main')).toBeInTheDocument()
    expect(screen.getByText('gpt-5-current')).toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
    expect(screen.queryByText('workspace-only')).not.toBeInTheDocument()
  })

  it('omits placeholder-only metadata without leaving normal-state badges behind', () => {
    render(
      <MemoryRouter>
        <SessionDetailHeader detail={sessionUiDetailScenarios.missingWorkContextAndModel} />
      </MemoryRouter>,
    )

    expect(screen.queryByText('作業コンテキスト不明')).not.toBeInTheDocument()
    expect(screen.queryByText('モデル不明')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
  })

  it('keeps degraded and workspace-only constraints visible in the header', () => {
    const { rerender } = render(
      <MemoryRouter>
        <SessionDetailHeader detail={sessionUiDetailScenarios.workspaceOnly} />
      </MemoryRouter>,
    )

    expect(screen.getByText('workspace-only')).toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <SessionDetailHeader detail={sessionUiDetailScenarios.interactionSurface} />
      </MemoryRouter>,
    )

    expect(screen.getByText('一部欠損あり')).toBeInTheDocument()
  })

  it('applies wrap-safe classes to long ids and metadata values', () => {
    render(
      <MemoryRouter>
        <SessionDetailHeader
          detail={buildSessionUiDetail({
            id: 'detail-session-with-an-extremely-long-identifier-that-needs-to-wrap-inside-the-header',
            work_context: {
              cwd: '/workspace/some/really/long/path/that/should/not/force/page-level-horizontal-scroll',
              git_root:
                '/workspace/some/really/long/path/that/should/not/force/page-level-horizontal-scroll',
              repository:
                'octo/copilot-cli-history-with-an-exceptionally-long-repository-name-for-wrap-testing',
              branch:
                'feature/detail-header-overflow-safe-rendering-with-very-long-branch-identifiers',
            },
            selected_model: 'gpt-5.4-with-a-very-long-suffix-for-overflow-checking',
          })}
        />
      </MemoryRouter>,
    )

    expect(
      screen.getByText(
        'detail-session-with-an-extremely-long-identifier-that-needs-to-wrap-inside-the-header',
      ),
    ).toHaveClass('break-all')
    expect(
      screen.getByText(
        'octo/copilot-cli-history-with-an-exceptionally-long-repository-name-for-wrap-testing @ feature/detail-header-overflow-safe-rendering-with-very-long-branch-identifiers',
      ),
    ).toHaveClass('break-words')
    expect(
      screen.getByText('gpt-5.4-with-a-very-long-suffix-for-overflow-checking'),
    ).toHaveClass('break-words')
  })

  it('shows created_at as 作成日時 when the session has never been updated', () => {
    render(
      <MemoryRouter>
        <SessionDetailHeader
          detail={buildSessionUiDetail({
            id: 'detail-created-only',
            created_at: '2026-04-26T09:00:00Z',
            updated_at: null,
          })}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('作成日時')).toBeInTheDocument()
    expect(screen.queryByText('更新日時')).not.toBeInTheDocument()
    expect(screen.getByText('2026-04-26 18:00:00 JST')).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import {
  buildSessionUiDetail,
  sessionUiDetailScenarios,
} from '../testing/sessionUiTestData.ts'
import SessionDetailHeader from '../../../../src/features/sessions/components/SessionDetailHeader.tsx'

describe('SessionDetailHeader', () => {
  /**
   * 概要・目的: 「shows only real metadata values for an ordinary complete session」を通じて、表示内容とアクセシビリティ上の見え方を検証する。
   * テストケース: 「shows only real metadata values for an ordinary complete session」の条件・入力・操作を実行する。
   * 期待値: only real metadata values for an ordinary complete session が表示されること。
   */
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

  /**
   * 概要・目的: 「omits placeholder-only metadata without leaving normal-state badges behind」を通じて、hook
   *   の状態遷移と非同期制御を検証する。
   * テストケース: 「omits placeholder-only metadata without leaving normal-state badges behind」の条件・入力・操作を実行する。
   * 期待値: placeholder-only metadata without leaving normal-state badges behind が含まれないこと。
   */
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

  /**
   * 概要・目的: 詳細ヘッダーで作業領域のみの制約は示しつつ、degraded ラベルを表示ノイズにしないことを検証する。
   * テストケース: workspace-only と degraded の detail を順にヘッダーへ渡す。
   * 期待値: workspace-only は表示され、degraded detail では「一部欠損あり」が表示されないこと。
   */
  it('keeps workspace-only visible while omitting the degraded badge', () => {
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

    expect(screen.queryByText('一部欠損あり')).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「applies wrap-safe classes to long ids and metadata values」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「applies wrap-safe classes to long ids and metadata values」の条件・入力・操作を実行する。
   * 期待値: wrap-safe classes to long ids and metadata values が適用されること。
   */
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

  /**
   * 概要・目的: 「shows created_at as 作成日時 when the session has never been updated」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「shows created_at as 作成日時 when the session has never been updated」の条件・入力・操作を実行する。
   * 期待値: created_at as 作成日時 when the session has never been updated が表示されること。
   */
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

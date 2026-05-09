import { render, screen } from '@testing-library/react'

import { buildSessionUiDetail } from '../testing/sessionUiTestData.ts'
import ActivityTimeline from '../../../../src/features/sessions/components/ActivityTimeline.tsx'

describe('ActivityTimeline', () => {
  /**
   * 概要・目的: 「renders raw payloads inside block-local horizontal scroll containers」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders raw payloads inside block-local horizontal scroll containers」の条件・入力・操作を実行する。
   * 期待値: raw payloads inside block-local horizontal scroll containers が画面に表示されること。
   */
  it('renders raw payloads inside block-local horizontal scroll containers', () => {
    render(
      <ActivityTimeline
        activity={buildSessionUiDetail().activity}
        rawIncluded
        rawStatus="included"
        onRequestRaw={() => {}}
        stateScopeKey="session:detail-interaction-surface"
      />,
    )

    expect(screen.getByText(/"type": "tool\.execution_start"/).closest('pre')).toHaveClass(
      'overflow-x-auto',
      'whitespace-pre',
    )
  })
})

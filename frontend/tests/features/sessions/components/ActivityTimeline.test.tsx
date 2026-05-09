import { render, screen } from '@testing-library/react'

import { buildSessionUiDetail } from '../testing/sessionUiTestData.ts'
import ActivityTimeline from '../../../../src/features/sessions/components/ActivityTimeline.tsx'

describe('ActivityTimeline', () => {
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

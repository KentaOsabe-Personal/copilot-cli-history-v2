import { render, screen } from '@testing-library/react'

import type { SessionIssue } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import IssueList from '../../../../src/features/sessions/components/IssueList.tsx'

describe('IssueList', () => {
  it('wraps long issue messages and source paths inside the issue panel', () => {
    const issues: readonly SessionIssue[] = [
      {
        code: 'session.partial',
        severity: 'warning',
        message:
          'issue-message-with-aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapInsideThePanel',
        source_path:
          '/tmp/copilot/session/a/very/long/path/with/no/natural/breakpoints/that/should/not/overflow/the/page/events.jsonl',
        scope: 'session',
        event_sequence: null,
      },
    ]

    render(<IssueList title="Session issues" issues={issues} />)

    expect(
      screen.getByText(
        'issue-message-with-aVeryLongTokenWithoutNaturalBreakpointsThatShouldWrapInsideThePanel',
      ),
    ).toHaveClass('whitespace-pre-wrap', 'break-words')
    expect(
      screen.getByText(
        '/tmp/copilot/session/a/very/long/path/with/no/natural/breakpoints/that/should/not/overflow/the/page/events.jsonl',
      ),
    ).toHaveClass('break-all')
  })
})

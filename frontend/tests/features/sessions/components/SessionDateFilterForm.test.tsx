import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { SessionDateRangeDraft } from '../../../../src/features/sessions/presentation/sessionDateFilter.ts'
import SessionDateFilterForm from '../../../../src/features/sessions/components/SessionDateFilterForm.tsx'

const DEFAULT_APPLIED_RANGE: SessionDateRangeDraft = {
  from: '2026-04-28',
  to: '2026-05-04',
}

function Harness({
  initialDraft,
  appliedRange = DEFAULT_APPLIED_RANGE,
  isApplying = false,
  onApply = vi.fn(async () => undefined),
}: {
  initialDraft: SessionDateRangeDraft
  appliedRange?: SessionDateRangeDraft
  isApplying?: boolean
  onApply?: (range: SessionDateRangeDraft) => void | Promise<void>
}) {
  const [draftRange, setDraftRange] = useState(initialDraft)

  return (
    <SessionDateFilterForm
      draftRange={draftRange}
      appliedRange={appliedRange}
      isApplying={isApplying}
      onDraftChange={setDraftRange}
      onApply={onApply}
    />
  )
}

describe('SessionDateFilterForm', () => {
  it('shows the current applied range and disables Apply while the draft range is invalid', () => {
    render(
      <Harness
        initialDraft={{
          from: '2026-05-08',
          to: '2026-05-07',
        }}
      />,
    )

    expect(screen.getByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toBeInTheDocument()
    expect(screen.getByText('開始日は終了日以前にしてください。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '適用する' })).toBeDisabled()
  })

  it('allows Apply again after the user fixes an invalid range', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn(async () => undefined)

    render(
      <Harness
        initialDraft={{
          from: '2026-05-08',
          to: '2026-05-07',
        }}
        onApply={onApply}
      />,
    )

    await user.clear(screen.getByLabelText('開始日'))
    await user.type(screen.getByLabelText('開始日'), '2026-05-06')
    await user.click(screen.getByRole('button', { name: '適用する' }))

    expect(screen.queryByText('開始日は終了日以前にしてください。')).not.toBeInTheDocument()
    expect(onApply).toHaveBeenCalledWith({
      from: '2026-05-06',
      to: '2026-05-07',
    })
  })

  it('accepts one-sided ranges as valid input', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn(async () => undefined)

    render(
      <Harness
        initialDraft={{
          from: '',
          to: '2026-05-07',
        }}
        onApply={onApply}
      />,
    )

    await user.click(screen.getByRole('button', { name: '適用する' }))

    expect(onApply).toHaveBeenCalledWith({
      from: '',
      to: '2026-05-07',
    })
  })

  it('allows submitting an empty draft as a reset back to the default range', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn(async () => undefined)

    render(
      <Harness
        initialDraft={{
          from: '2026-05-01',
          to: '2026-05-07',
        }}
        onApply={onApply}
      />,
    )

    await user.clear(screen.getByLabelText('開始日'))
    await user.clear(screen.getByLabelText('終了日'))
    await user.click(screen.getByRole('button', { name: '適用する' }))

    expect(onApply).toHaveBeenCalledWith({
      from: '',
      to: '',
    })
  })
})

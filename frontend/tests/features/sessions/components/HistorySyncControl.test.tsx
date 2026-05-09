import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import HistorySyncControl from '../../../../src/features/sessions/components/HistorySyncControl.tsx'

describe('HistorySyncControl', () => {
  it('renders a retryable sync button by default and starts sync on click', async () => {
    const user = userEvent.setup()
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing={false} onSync={onSync} />)

    const button = screen.getByRole('button', { name: '履歴を最新化' })

    expect(button).toBeEnabled()

    await user.click(button)

    expect(onSync).toHaveBeenCalledTimes(1)
  })

  it('disables the button and updates the label while syncing', () => {
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing onSync={onSync} />)

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
  })

  it('starts sync from keyboard activation', async () => {
    const user = userEvent.setup()
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing={false} onSync={onSync} />)

    await user.tab()
    await user.keyboard('{Enter}')

    expect(onSync).toHaveBeenCalledTimes(1)
  })
})

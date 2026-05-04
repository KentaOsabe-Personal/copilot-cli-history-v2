import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import SessionEmptyState from './SessionEmptyState.tsx'

describe('SessionEmptyState', () => {
  it('renders a primary action that starts the same sync request', async () => {
    const user = userEvent.setup()
    const onSync = vi.fn()

    render(
      <SessionEmptyState
        appliedRangeLabel="直近 7 日"
        syncState={{ status: 'idle' }}
        isSyncing={false}
        onSync={onSync}
      />,
    )

    expect(screen.getByRole('heading', { name: 'この日付範囲に一致するセッションはありません' })).toBeInTheDocument()
    expect(screen.getByText('現在の表示範囲: 直近 7 日')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '履歴を取り込む' }))

    expect(onSync).toHaveBeenCalledTimes(1)
  })

  it('disables the empty-state action while syncing', () => {
    const onSync = vi.fn()

    render(
      <SessionEmptyState
        appliedRangeLabel="2026-05-01 〜 2026-05-07"
        syncState={{ status: 'syncing' }}
        isSyncing
        onSync={onSync}
      />,
    )

    expect(screen.getByRole('button', { name: '履歴を取り込み中...' })).toBeDisabled()
  })

  it('keeps the empty meaning range-scoped and adds synced_empty only as a hint', () => {
    render(
      <SessionEmptyState
        appliedRangeLabel="2026-05-01 〜 2026-05-07"
        syncState={{
          status: 'synced_empty',
          result: {
            sync_run: {
              id: 42,
              status: 'completed',
              started_at: '2026-04-30T09:00:00Z',
              finished_at: '2026-04-30T09:00:03Z',
            },
            counts: {
              processed_count: 1,
              inserted_count: 0,
              updated_count: 0,
              saved_count: 0,
              skipped_count: 1,
              failed_count: 0,
              degraded_count: 0,
            },
          },
        }}
        isSyncing={false}
        onSync={vi.fn()}
      />,
    )

    expect(screen.getByText('現在の表示範囲: 2026-05-01 〜 2026-05-07')).toBeInTheDocument()
    expect(screen.getByText('この条件では、まだ一致するセッションが見つかっていません。')).toBeInTheDocument()
  })
})

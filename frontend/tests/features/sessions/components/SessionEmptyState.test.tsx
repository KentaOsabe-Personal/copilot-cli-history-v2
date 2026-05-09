import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import SessionEmptyState from '../../../../src/features/sessions/components/SessionEmptyState.tsx'

describe('SessionEmptyState', () => {
  /**
   * 概要・目的: 「renders a primary action that starts the same sync request」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a primary action that starts the same sync request」の条件・入力・操作を実行する。
   * 期待値: a primary action that starts the same sync request が画面に表示されること。
   */
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

  /**
   * 概要・目的: 「disables the empty-state action while syncing」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「disables the empty-state action while syncing」の条件・入力・操作を実行する。
   * 期待値: 「disables the empty-state action while syncing」で示す状態または振る舞いが成立すること。
   */
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

  /**
   * 概要・目的: 「keeps the empty meaning range-scoped and adds synced_empty only as a
   *   hint」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps the empty meaning range-scoped and adds synced_empty only as a hint」の条件・入力・操作を実行する。
   * 期待値: the empty meaning range-scoped が維持され、adds synced_empty only as a hintこと。
   */
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

  /**
   * 概要・目的: 「renders a search-scoped empty state without offering edit, delete, or share actions」を通じて、検索・日付条件と
   *   query 組み立てを検証する。
   * テストケース: 「renders a search-scoped empty state without offering edit, delete, or share
   *   actions」の条件・入力・操作を実行する。
   * 期待値: a search-scoped empty state without offering edit, delete, or share actions が画面に表示されること。
   */
  it('renders a search-scoped empty state without offering edit, delete, or share actions', async () => {
    const user = userEvent.setup()
    const onClearSearch = vi.fn()

    render(
      <SessionEmptyState
        appliedRangeLabel="2026-05-01 〜 2026-05-07"
        appliedSearchTerm="apply patch"
        syncState={{ status: 'idle' }}
        isSyncing={false}
        onSync={vi.fn()}
        onClearSearch={onClearSearch}
      />,
    )

    expect(screen.getByRole('heading', { name: '検索条件に一致するセッションはありません' })).toBeInTheDocument()
    expect(screen.getByText('現在の表示条件: 2026-05-01 〜 2026-05-07 / 検索: apply patch')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /編集|削除|共有/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '検索を解除' }))

    expect(onClearSearch).toHaveBeenCalledTimes(1)
  })
})

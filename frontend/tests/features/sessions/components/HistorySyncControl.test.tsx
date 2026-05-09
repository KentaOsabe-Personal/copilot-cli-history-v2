import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import HistorySyncControl from '../../../../src/features/sessions/components/HistorySyncControl.tsx'

describe('HistorySyncControl', () => {
  /**
   * 概要・目的: 「renders a retryable sync button by default and starts sync on click」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a retryable sync button by default and starts sync on click」の条件・入力・操作を実行する。
   * 期待値: a retryable sync button by default が表示され、click で sync が開始されること。
   */
  it('renders a retryable sync button by default and starts sync on click', async () => {
    const user = userEvent.setup()
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing={false} onSync={onSync} />)

    const button = screen.getByRole('button', { name: '履歴を最新化' })

    expect(button).toBeEnabled()

    await user.click(button)

    expect(onSync).toHaveBeenCalledTimes(1)
  })

  /**
   * 概要・目的: 「disables the button and updates the label while syncing」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「disables the button and updates the label while syncing」の条件・入力・操作を実行する。
   * 期待値: the button が disabled になり、the label while syncing が更新されること。
   */
  it('disables the button and updates the label while syncing', () => {
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing onSync={onSync} />)

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
  })

  /**
   * 概要・目的: 「starts sync from keyboard activation」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「starts sync from keyboard activation」の条件・入力・操作を実行する。
   * 期待値: keyboard activation から sync が開始されること。
   */
  it('starts sync from keyboard activation', async () => {
    const user = userEvent.setup()
    const onSync = vi.fn()

    render(<HistorySyncControl isSyncing={false} onSync={onSync} />)

    await user.tab()
    await user.keyboard('{Enter}')

    expect(onSync).toHaveBeenCalledTimes(1)
  })
})

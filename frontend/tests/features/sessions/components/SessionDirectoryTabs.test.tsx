import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import SessionDirectoryTabs from '../../../../src/features/sessions/components/SessionDirectoryTabs.tsx'
import type {
  SessionDirectoryTab,
  SessionDirectoryTabKey,
} from '../../../../src/features/sessions/presentation/sessionDirectoryTabs.ts'

const tabs: readonly SessionDirectoryTab[] = [
  {
    key: 'all',
    kind: 'all',
    label: 'すべて',
    contextLabel: null,
    fullPath: null,
    count: 4,
  },
  {
    key: 'cwd:/workspace/team/frontend/app',
    kind: 'directory',
    label: 'app',
    contextLabel: 'team/frontend',
    fullPath: '/workspace/team/frontend/app',
    count: 2,
  },
  {
    key: 'cwd:/workspace/admin/frontend/app',
    kind: 'directory',
    label: 'app',
    contextLabel: 'admin/frontend',
    fullPath: '/workspace/admin/frontend/app',
    count: 1,
  },
  {
    key: 'unset',
    kind: 'unset',
    label: 'ディレクトリ未設定',
    contextLabel: null,
    fullPath: null,
    count: 1,
  },
]

function getTabId(key: SessionDirectoryTabKey): string {
  return `directory-tab-${key.replaceAll(/[^a-zA-Z0-9_-]/g, '-')}`
}

describe('SessionDirectoryTabs', () => {
  /**
   * 概要・目的: 作業ディレクトリ別タブが tablist / tab として件数・範囲・完全パスを支援技術へ伝える契約を検証する。
   * テストケース: all、同一 basename の directory、未設定タブを描画する。
   * 期待値: tablist と各 tab に件数を含む accessible name、選択状態、tabpanel 参照、完全パス title が設定されること。
   */
  it('renders accessible tabs with counts, selected state, and panel references', () => {
    render(
      <SessionDirectoryTabs
        tabs={tabs}
        selectedKey="cwd:/workspace/team/frontend/app"
        panelId="session-directory-panel"
        getTabId={getTabId}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByRole('tablist', { name: '作業ディレクトリ別セッション一覧タブ、全 4 件' })).toBeInTheDocument()

    const selectedTab = screen.getByRole('tab', {
      name: 'team/frontend / app、2 件、完全パス /workspace/team/frontend/app',
    })

    expect(selectedTab).toHaveAttribute('id', 'directory-tab-cwd--workspace-team-frontend-app')
    expect(selectedTab).toHaveAttribute('aria-selected', 'true')
    expect(selectedTab).toHaveAttribute('aria-controls', 'session-directory-panel')
    expect(selectedTab).toHaveAttribute('title', '/workspace/team/frontend/app')
    expect(screen.getByRole('tab', { name: 'すべて、4 件' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tab', { name: 'ディレクトリ未設定、1 件、作業ディレクトリ未設定' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: クリックまたはタップ相当の操作で、選択するタブ key だけを親へ通知する契約を検証する。
   * テストケース: 未設定タブをクリックする。
   * 期待値: `onSelect` が `unset` で 1 回呼ばれ、検索や取得条件には触れない単純な選択イベントになること。
   */
  it('calls onSelect when a tab is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()

    render(
      <SessionDirectoryTabs
        tabs={tabs}
        selectedKey="all"
        panelId="session-directory-panel"
        getTabId={getTabId}
        onSelect={onSelect}
      />,
    )

    await user.click(screen.getByRole('tab', { name: 'ディレクトリ未設定、1 件、作業ディレクトリ未設定' }))

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('unset')
  })

  /**
   * 概要・目的: キーボード利用者が左右キーで隣接タブへ移動でき、端で循環する契約を検証する。
   * テストケース: 最初のタブで ArrowLeft、最後のタブで ArrowRight を押す。
   * 期待値: ArrowLeft は最後の未設定タブ、ArrowRight は最初の `すべて` タブを選択すること。
   */
  it('selects adjacent tabs with wrapping ArrowLeft and ArrowRight behavior', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const { rerender } = render(
      <SessionDirectoryTabs
        tabs={tabs}
        selectedKey="all"
        panelId="session-directory-panel"
        getTabId={getTabId}
        onSelect={onSelect}
      />,
    )

    screen.getByRole('tab', { name: 'すべて、4 件' }).focus()
    await user.keyboard('{ArrowLeft}')

    expect(onSelect).toHaveBeenLastCalledWith('unset')

    rerender(
      <SessionDirectoryTabs
        tabs={tabs}
        selectedKey="unset"
        panelId="session-directory-panel"
        getTabId={getTabId}
        onSelect={onSelect}
      />,
    )

    screen.getByRole('tab', { name: 'ディレクトリ未設定、1 件、作業ディレクトリ未設定' }).focus()
    await user.keyboard('{ArrowRight}')

    expect(onSelect).toHaveBeenLastCalledWith('all')
  })
})

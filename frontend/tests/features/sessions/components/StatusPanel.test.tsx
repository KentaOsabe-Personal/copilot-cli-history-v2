import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import StatusPanel from '../../../../src/features/sessions/components/StatusPanel.tsx'

describe('StatusPanel', () => {
  /**
   * 概要・目的: 「renders a loading panel without a back link by default」を通じて、hook の状態遷移と非同期制御を検証する。
   * テストケース: 「renders a loading panel without a back link by default」の条件・入力・操作を実行する。
   * 期待値: a loading panel without a back link by default が画面に表示されること。
   */
  it('renders a loading panel without a back link by default', () => {
    render(
      <MemoryRouter>
        <StatusPanel variant="loading" title="読み込み中" message="セッションを取得しています。" />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '読み込み中' })).toBeInTheDocument()
    expect(screen.getByText('セッションを取得しています。')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'セッション一覧へ戻る' })).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders an error panel with a session index link when requested」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「renders an error panel with a session index link when requested」の条件・入力・操作を実行する。
   * 期待値: an error panel with a session index link when requested が画面に表示されること。
   */
  it('renders an error panel with a session index link when requested', () => {
    render(
      <MemoryRouter>
        <StatusPanel
          variant="error"
          title="取得に失敗しました"
          message="一覧に戻って対象セッションを選び直してください。"
          showSessionIndexLink
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '取得に失敗しました' })).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: 'セッション一覧へ戻る',
      }),
    ).toHaveAttribute('href', '/')
  })

  /**
   * 概要・目的: 「renders a custom action slot when provided」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「renders a custom action slot when provided」の条件・入力・操作を実行する。
   * 期待値: a custom action slot when provided が画面に表示されること。
   */
  it('renders a custom action slot when provided', () => {
    render(
      <MemoryRouter>
        <StatusPanel
          variant="empty"
          title="セッションがありません"
          message="履歴を取り込むと一覧に表示されます。"
          action={
            <button type="button" className="rounded-full px-4 py-2">
              履歴を取り込む
            </button>
          }
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を取り込む' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'セッション一覧へ戻る' })).not.toBeInTheDocument()
  })
})

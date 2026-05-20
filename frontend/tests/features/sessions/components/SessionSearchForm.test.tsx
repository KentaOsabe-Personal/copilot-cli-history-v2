import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import SessionSearchForm from '../../../../src/features/sessions/components/SessionSearchForm.tsx'

describe('SessionSearchForm', () => {
  /**
   * 概要・目的: 「applies a search term with submit and keeps the applied criteria visible」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「applies a search term with submit and keeps the applied criteria visible」の条件・入力・操作を実行する。
   * 期待値: a search term with submit and keeps the applied criteria visible が適用されること。
   */
  it('applies a search term with submit and keeps the applied criteria visible', async () => {
    const user = userEvent.setup()
    const onApplySearch = vi.fn()

    render(
      <SessionSearchForm
        appliedSearchTerm="apply patch"
        appliedCriteriaLabel="2026-04-28 〜 2026-05-04 / 検索: apply patch"
        isApplying={false}
        backendErrorMessage={null}
        onApplySearch={onApplySearch}
        onClearSearch={vi.fn()}
      />,
    )

    expect(screen.getByText('現在の検索条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch')).toBeInTheDocument()
    expect(screen.getByText('会話本文、会話 preview、issue、実行ディレクトリの内容を検索します。')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('検索語'))
    await user.type(screen.getByLabelText('検索語'), 'tool failure')
    await user.click(screen.getByRole('button', { name: '検索する' }))

    expect(onApplySearch).toHaveBeenCalledWith('tool failure')
  })

  /**
   * 概要・目的: 「applies a search term with Enter」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「applies a search term with Enter」の条件・入力・操作を実行する。
   * 期待値: a search term with Enter が適用されること。
   */
  it('applies a search term with Enter', async () => {
    const user = userEvent.setup()
    const onApplySearch = vi.fn()

    render(
      <SessionSearchForm
        appliedSearchTerm=""
        appliedCriteriaLabel="直近 7 日"
        isApplying={false}
        backendErrorMessage={null}
        onApplySearch={onApplySearch}
        onClearSearch={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('検索語'), 'gpt-5{Enter}')

    expect(onApplySearch).toHaveBeenCalledWith('gpt-5')
  })

  /**
   * 概要・目的: 「clears the applied search without changing the date criteria」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「clears the applied search without changing the date criteria」の条件・入力・操作を実行する。
   * 期待値: 「clears the applied search without changing the date criteria」で示す状態または振る舞いが成立すること。
   */
  it('clears the applied search without changing the date criteria', async () => {
    const user = userEvent.setup()
    const onClearSearch = vi.fn()

    render(
      <SessionSearchForm
        appliedSearchTerm="apply patch"
        appliedCriteriaLabel="2026-04-28 〜 2026-05-04 / 検索: apply patch"
        isApplying={false}
        backendErrorMessage={null}
        onApplySearch={vi.fn()}
        onClearSearch={onClearSearch}
      />,
    )

    await user.click(screen.getByRole('button', { name: '検索を解除' }))

    expect(onClearSearch).toHaveBeenCalledTimes(1)
  })

  /**
   * 概要・目的: 「shows frontend and backend search-condition errors apart from generic fetch errors」を通じて、検索・日付条件と
   *   query 組み立てを検証する。
   * テストケース: 「shows frontend and backend search-condition errors apart from generic fetch
   *   errors」の条件・入力・操作を実行する。
   * 期待値: frontend and backend search-condition errors apart from generic fetch errors が表示されること。
   */
  it('shows frontend and backend search-condition errors apart from generic fetch errors', async () => {
    const user = userEvent.setup()
    const onApplySearch = vi.fn()

    const { rerender } = render(
      <SessionSearchForm
        appliedSearchTerm=""
        appliedCriteriaLabel="直近 7 日"
        isApplying={false}
        backendErrorMessage={null}
        onApplySearch={onApplySearch}
        onClearSearch={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('検索語'), 'a'.repeat(201))
    await user.click(screen.getByRole('button', { name: '検索する' }))

    expect(screen.getByRole('alert')).toHaveTextContent('検索語は 200 文字以内で入力してください。')
    expect(onApplySearch).not.toHaveBeenCalled()

    rerender(
      <SessionSearchForm
        appliedSearchTerm=""
        appliedCriteriaLabel="直近 7 日"
        isApplying={false}
        backendErrorMessage="検索条件を確認してください。"
        onApplySearch={onApplySearch}
        onClearSearch={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('検索条件を確認してください。')
  })
})

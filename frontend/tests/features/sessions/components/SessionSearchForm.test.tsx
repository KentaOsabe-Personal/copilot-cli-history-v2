import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import SessionSearchForm from '../../../../src/features/sessions/components/SessionSearchForm.tsx'

describe('SessionSearchForm', () => {
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
    expect(screen.getByText('会話本文、会話 preview、issue の内容を検索します。')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('検索語'))
    await user.type(screen.getByLabelText('検索語'), 'tool failure')
    await user.click(screen.getByRole('button', { name: '検索する' }))

    expect(onApplySearch).toHaveBeenCalledWith('tool failure')
  })

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

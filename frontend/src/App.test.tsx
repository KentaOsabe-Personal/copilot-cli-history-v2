import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import App from './App'

function expectReadOnlyControlsToBeAbsent() {
  expect(screen.queryByRole('button', { name: '検索' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '絞り込み' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '再読み込み' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '自動更新' })).not.toBeInTheDocument()
}

function expectReadOnlyScopeCopy() {
  expect(screen.getByText('この画面は閲覧専用です。')).toBeInTheDocument()
  expect(
    screen.getByText(
      'セッション一覧では日付範囲だけで絞り込めます。検索、repository / branch / model などの追加条件、編集、削除、共有、自動更新は提供しません。',
    ),
  ).toBeInTheDocument()
  expect(
    screen.queryByText(
      'セッション一覧と詳細表示だけをこの UI の対象にし、編集や削除、検索、絞り込み、再読み込み、自動更新は提供しません。',
    ),
  ).not.toBeInTheDocument()
}

describe('App', () => {
  it('renders the session index route inside the shared read-only shell', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(
      screen.getByRole('heading', {
        name: 'Copilot CLI Session History',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'セッション一覧' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('heading', { name: 'セッション一覧' })).toBeInTheDocument()
    expectReadOnlyScopeCopy()
    expectReadOnlyControlsToBeAbsent()
  })

  it('renders the detail route directly without going through the index page', () => {
    render(
      <MemoryRouter initialEntries={['/sessions/session-123']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'セッション詳細' })).toBeInTheDocument()
    expect(screen.getByText('session-123')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'セッション一覧' })).toHaveAttribute('href', '/')
    expectReadOnlyScopeCopy()
    expectReadOnlyControlsToBeAbsent()
  })
})

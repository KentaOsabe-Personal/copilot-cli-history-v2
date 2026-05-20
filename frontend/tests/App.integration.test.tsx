import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  HistorySyncResponse,
  SessionApiClient,
  SessionApiResult,
  SessionIndexResponse,
  SessionSummary,
} from '../src/features/sessions/api/sessionApi.types.ts'
import {
  buildDefaultRange,
  toSessionIndexQuery,
} from '../src/features/sessions/presentation/sessionDateFilter.ts'

const { sessionApiClientMock } = vi.hoisted(() => ({
  sessionApiClientMock: {
    fetchSessionIndex: vi.fn<SessionApiClient['fetchSessionIndex']>(),
    fetchSessionDetail: vi.fn<SessionApiClient['fetchSessionDetail']>(),
    fetchSessionDetailWithRaw: vi.fn<SessionApiClient['fetchSessionDetailWithRaw']>(),
    syncHistory: vi.fn<SessionApiClient['syncHistory']>(),
  },
}))

vi.mock('../src/features/sessions/api/sessionApi.ts', () => ({
  createSessionApiClient: vi.fn(() => sessionApiClientMock),
  sessionApiClient: sessionApiClientMock,
}))

import App from '../src/App'

const FIXED_NOW = new Date('2026-05-03T18:15:00Z')

function deferred<T>() {
  let resolve!: (value: T) => void

  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })

  return { promise, resolve }
}

function buildSessionSummary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: 'current-session',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: {
      cwd: '/workspace/current-session',
      git_root: '/workspace/current-session',
      repository: 'octo/example',
      branch: 'main',
    },
    selected_model: 'gpt-5.4',
    source_state: 'complete',
    event_count: 5,
    message_snapshot_count: 3,
    conversation_summary: {
      has_conversation: true,
      message_count: 2,
      preview: '履歴を確認したい',
      activity_count: 3,
    },
    degraded: false,
    issues: [],
    ...overrides,
  }
}

function buildIndexResponse(
  data: readonly SessionSummary[],
): SessionApiResult<SessionIndexResponse> {
  return {
    status: 'success',
    data: {
      data,
      meta: {
        count: data.length,
        partial_results: false,
      },
    },
  }
}

function buildSyncResponse(): SessionApiResult<HistorySyncResponse> {
  return {
    status: 'success',
    data: {
      data: {
        sync_run: {
          id: 42,
          status: 'completed',
          started_at: '2026-04-30T09:00:00Z',
          finished_at: '2026-04-30T09:00:03Z',
        },
        counts: {
          processed_count: 5,
          inserted_count: 2,
          updated_count: 1,
          saved_count: 3,
          skipped_count: 2,
          failed_count: 0,
          degraded_count: 0,
        },
      },
    },
  }
}

describe('App integration', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(FIXED_NOW)
    sessionApiClientMock.fetchSessionIndex.mockReset()
    sessionApiClientMock.fetchSessionDetail.mockReset()
    sessionApiClientMock.fetchSessionDetailWithRaw.mockReset()
    sessionApiClientMock.syncHistory.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  /**
   * 概要・目的: 「keeps the read-only scope copy and latest applied date range through a same-range sync
   *   refresh」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps the read-only scope copy and latest applied date range through a same-range sync
   *   refresh」の条件・入力・操作を実行する。
   * 期待値: the read-only scope copy が維持され、latest applied date range through a same-range sync refreshこと。
   */
  it(
    'keeps the read-only scope copy and latest applied date range through a same-range sync refresh',
    async () => {
      const defaultQuery = toSessionIndexQuery(buildDefaultRange(new Date()))
      const refreshRequest = deferred<SessionApiResult<SessionIndexResponse>>()
      const filteredSessions = [
        buildSessionSummary({
          id: 'current-filtered-session',
          source_format: 'current',
        }),
        buildSessionSummary({
          id: 'legacy-filtered-session',
          source_format: 'legacy',
          selected_model: null,
        }),
      ] as const
      const refreshedSessions = [
        ...filteredSessions,
        buildSessionSummary({
          id: 'current-filtered-session-after-sync',
          source_format: 'current',
        }),
      ] as const

      sessionApiClientMock.fetchSessionIndex
        .mockResolvedValueOnce(buildIndexResponse([buildSessionSummary()]))
        .mockResolvedValueOnce(buildIndexResponse(filteredSessions))
        .mockReturnValueOnce(refreshRequest.promise)
      sessionApiClientMock.syncHistory.mockResolvedValue(buildSyncResponse())

      render(
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>,
      )

      await waitFor(() =>
        expect(screen.getByRole('link', { name: 'current-session を開く' })).toBeInTheDocument(),
      )

      expect(screen.getByText('この画面は閲覧専用です。')).toBeInTheDocument()
      expect(
        screen.getByText(
          'セッション一覧では日付範囲と検索語で絞り込めます。検索語は会話本文、preview、issue、実行ディレクトリを対象にします。repository / branch / model の専用フィルタ、編集、削除、共有、自動更新は提供しません。',
        ),
      ).toBeInTheDocument()
      expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({
          query: defaultQuery,
          signal: expect.any(AbortSignal),
        }),
      )

      fireEvent.change(screen.getByLabelText('開始日'), {
        target: { value: '2026-05-01' },
      })
      fireEvent.change(screen.getByLabelText('終了日'), {
        target: { value: '' },
      })
      fireEvent.click(screen.getByRole('button', { name: '適用する' }))

      await waitFor(() =>
        expect(screen.getByText('現在の表示範囲: 2026-05-01 以降')).toBeInTheDocument(),
      )
      expect(
        screen.getByRole('link', { name: 'current-filtered-session を開く' }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'legacy-filtered-session を開く' }),
      ).toBeInTheDocument()
      expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({
          query: {
            from: '2026-05-01T00:00:00+09:00',
          },
          signal: expect.any(AbortSignal),
        }),
      )

      fireEvent.click(screen.getByRole('button', { name: '履歴を最新化' }))

      await waitFor(() => expect(sessionApiClientMock.syncHistory).toHaveBeenCalledTimes(1))
      await waitFor(() =>
        expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenCalledTimes(3),
      )

      expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
      expect(
        screen.getByRole('link', { name: 'legacy-filtered-session を開く' }),
      ).toBeInTheDocument()
      expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenNthCalledWith(
        3,
        expect.objectContaining({
          query: {
            from: '2026-05-01T00:00:00+09:00',
          },
          signal: expect.any(AbortSignal),
        }),
      )

      refreshRequest.resolve(buildIndexResponse(refreshedSessions))

      await waitFor(() =>
        expect(screen.getByRole('heading', { name: '履歴を最新化しました' })).toBeInTheDocument(),
      )

      expect(screen.getByText('3 件を保存しました。')).toBeInTheDocument()
      expect(screen.getByText('現在の表示範囲: 2026-05-01 以降')).toBeInTheDocument()
      expect(
        screen.getByRole('link', {
          name: 'current-filtered-session-after-sync を開く',
        }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: 'legacy-filtered-session を開く' }),
      ).toBeInTheDocument()
      expect(screen.getByText('この画面は閲覧専用です。')).toBeInTheDocument()
      expect(
        screen.getByText(
          'セッション一覧では日付範囲と検索語で絞り込めます。検索語は会話本文、preview、issue、実行ディレクトリを対象にします。repository / branch / model の専用フィルタ、編集、削除、共有、自動更新は提供しません。',
        ),
      ).toBeInTheDocument()
    },
  )

  /**
   * 概要・目的: cwd 由来の検索語を一覧画面で適用・解除しても、現在の日付範囲と条件表示、カードの実行ディレクトリ表示が保たれることを検証する。
   * テストケース: 初期一覧表示後に実行ディレクトリの一部で検索し、その検索を解除する。
   * 期待値: 検索 request は日付範囲と search を併用し、検索結果カードに cwd / repository / branch / preview が併存し、解除後は同じ日付範囲で検索語なしに戻ること。
   */
  it('applies and clears cwd search while keeping the date range and visible card context', async () => {
    const defaultQuery = toSessionIndexQuery(buildDefaultRange(new Date()))
    const cwdSearchSession = buildSessionSummary({
      id: 'cwd-search-result',
      work_context: {
        cwd: '/Users/example/work/current-session/frontend',
        git_root: '/Users/example/work/current-session',
        repository: 'octo/current-session',
        branch: 'feature/cwd-search',
      },
      conversation_summary: {
        has_conversation: true,
        message_count: 2,
        preview: 'cwd 検索で見つかった会話',
        activity_count: 1,
      },
    })
    sessionApiClientMock.fetchSessionIndex
      .mockResolvedValueOnce(buildIndexResponse([buildSessionSummary()]))
      .mockResolvedValueOnce(buildIndexResponse([cwdSearchSession]))
      .mockResolvedValueOnce(buildIndexResponse([buildSessionSummary({ id: 'cleared-session' })]))

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'current-session を開く' })).toBeInTheDocument(),
    )

    fireEvent.change(screen.getByLabelText('検索語'), {
      target: { value: ' current-session/frontend ' },
    })
    fireEvent.click(screen.getByRole('button', { name: '検索する' }))

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'cwd-search-result を開く' })).toBeInTheDocument(),
    )

    expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: {
          ...defaultQuery,
          search: 'current-session/frontend',
        },
        signal: expect.any(AbortSignal),
      }),
    )
    expect(
      screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: current-session/frontend の検索結果を表示しています。'),
    ).toBeInTheDocument()
    expect(screen.getByText('実行ディレクトリ')).toBeInTheDocument()
    expect(screen.getByText('/Users/example/work/current-session/frontend')).toBeInTheDocument()
    expect(screen.getByText('octo/current-session @ feature/cwd-search')).toBeInTheDocument()
    expect(screen.getByText('cwd 検索で見つかった会話')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '検索を解除' }))

    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'cleared-session を開く' })).toBeInTheDocument(),
    )
    expect(sessionApiClientMock.fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: defaultQuery,
        signal: expect.any(AbortSignal),
      }),
    )
  })
})

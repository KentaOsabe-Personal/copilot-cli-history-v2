import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SessionSummary } from '../api/sessionApi.types.ts'
import type { HistorySyncState, UseHistorySyncResult } from '../hooks/useHistorySync.ts'
import { useHistorySync } from '../hooks/useHistorySync.ts'
import type { SessionIndexState, UseSessionIndexResult } from '../hooks/useSessionIndex.ts'
import { useSessionIndex } from '../hooks/useSessionIndex.ts'
import type { SessionDateRangeDraft } from '../presentation/sessionDateFilter.ts'
import SessionIndexPage from './SessionIndexPage.tsx'

vi.mock('../hooks/useHistorySync.ts', () => ({
  useHistorySync: vi.fn(),
}))

vi.mock('../hooks/useSessionIndex.ts', () => ({
  useSessionIndex: vi.fn(),
}))

const mockedUseHistorySync = vi.mocked(useHistorySync)
const mockedUseSessionIndex = vi.mocked(useSessionIndex)
const DEFAULT_APPLIED_RANGE: SessionDateRangeDraft = {
  from: '2026-04-28',
  to: '2026-05-04',
}

function buildUseSessionIndexResult(
  state: SessionIndexState,
  appliedRange: SessionDateRangeDraft = DEFAULT_APPLIED_RANGE,
): UseSessionIndexResult {
  const reloadOutcome =
    state.status === 'loading'
      ? ({ status: 'empty' } as const)
      : state

  return {
    state,
    appliedRange,
    isRefreshing: false,
    applyRange: vi.fn(async () => reloadOutcome),
    reloadSessions: async () => reloadOutcome,
  }
}

function buildUseHistorySyncResult(
  state: HistorySyncState = { status: 'idle' },
  overrides: Partial<Pick<UseHistorySyncResult, 'isSyncing' | 'startSync'>> = {},
): UseHistorySyncResult {
  return {
    state,
    isSyncing: state.status === 'syncing',
    startSync: vi.fn(async () => undefined),
    ...overrides,
  }
}

function buildSessionSummary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: 'session-123',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: {
      cwd: '/workspace/session-123',
      git_root: '/workspace/session-123',
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

describe('SessionIndexPage', () => {
  beforeEach(() => {
    mockedUseHistorySync.mockReset()
    mockedUseSessionIndex.mockReset()
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult())
  })

  it('renders a loading panel while the session index is being fetched', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'loading' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'セッション一覧' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を読み込んでいます' })).toBeInTheDocument()
  })

  it('renders an empty-state sync action when the backend returns no sessions', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'この日付範囲に一致するセッションはありません' })).toBeInTheDocument()
    expect(screen.getByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '履歴を取り込む' })).toBeInTheDocument()
  })

  it('keeps a user-selected empty range visible in the empty state copy', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'empty' },
        {
          from: '2026-05-01',
          to: '2026-05-07',
        },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('現在の表示範囲: 2026-05-01 〜 2026-05-07')).toBeInTheDocument()
  })

  it('renders ordered session cards without placeholder-only work context or model metadata', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'session-b',
          updated_at: '2026-04-26T10:05:00Z',
          degraded: true,
        }),
        buildSessionSummary({
          id: 'session-a',
          updated_at: null,
          work_context: {
            cwd: null,
            git_root: null,
            repository: null,
            branch: null,
          },
          selected_model: null,
        }),
      ],
      meta: {
        count: 2,
        partial_results: true,
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /を開く$/ }).map((node) => node.getAttribute('href'))).toEqual([
      '/sessions/session-b',
      '/sessions/session-a',
    ])
    expect(screen.getAllByText('一部欠損あり')).toHaveLength(1)
    expect(screen.getByText('時刻不明')).toBeInTheDocument()
    expect(screen.queryByText('作業コンテキスト不明')).not.toBeInTheDocument()
    expect(screen.queryByText('モデル不明')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-b を開く' })).toHaveAttribute(
      'href',
      '/sessions/session-b',
    )
  })

  it('keeps normal sessions free of always-on status badges while surfacing exceptional states', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'conversation-session',
          updated_at: '2026-04-26T10:05:00Z',
          conversation_summary: {
            has_conversation: true,
            message_count: 4,
            preview: '次の実装方針を相談したい',
            activity_count: 7,
          },
        }),
        buildSessionSummary({
          id: 'metadata-only-session',
          conversation_summary: {
            has_conversation: false,
            message_count: 0,
            preview: null,
            activity_count: 0,
          },
        }),
        buildSessionSummary({
          id: 'workspace-only-session',
          source_state: 'workspace_only',
          conversation_summary: {
            has_conversation: false,
            message_count: 0,
            preview: null,
            activity_count: 0,
          },
        }),
      ],
      meta: {
        count: 3,
        partial_results: false,
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByText('4 件の会話')).toBeInTheDocument()
    expect(screen.getByText('次の実装方針を相談したい')).toBeInTheDocument()
    expect(screen.getByText('2026-04-26 19:05:00 JST')).toBeInTheDocument()
    expect(screen.queryByText('会話あり')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
    expect(screen.queryByText('complete')).not.toBeInTheDocument()
    expect(screen.queryByText('7 件の内部 activity')).not.toBeInTheDocument()
    expect(screen.getByText('metadata-only')).toBeInTheDocument()
    expect(screen.getByText('workspace-only')).toBeInTheDocument()
    expect(screen.getAllByText('表示できる会話本文はありません')).toHaveLength(2)
  })

  it('renders an error panel without success cards when the fetch fails', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 503,
        code: 'root_missing',
        message: 'history root does not exist',
        details: {
          path: '/tmp/.copilot',
        },
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を表示できません' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'session-123 を開く' })).not.toBeInTheDocument()
  })

  it('navigates to the detail route when a session card is selected', async () => {
    const user = userEvent.setup()

    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'session-123',
        }),
      ],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<SessionIndexPage />} />
          <Route path="/sessions/:sessionId" element={<p>detail route</p>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: 'session-123 を開く' }))

    expect(screen.getByText('detail route')).toBeInTheDocument()
  })

  it('starts the same sync request from the top control and the empty-state action', async () => {
    const user = userEvent.setup()
    const startSync = vi.fn(async () => undefined)

    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(
      buildUseHistorySyncResult({ status: 'idle' }, { startSync }),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: '履歴を最新化' }))
    await user.click(screen.getByRole('button', { name: '履歴を取り込む' }))

    expect(startSync).toHaveBeenCalledTimes(2)
  })

  it('disables both sync actions while syncing from an empty page', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({ status: 'syncing' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '履歴を取り込み中...' })).toBeDisabled()
  })

  it('renders synced sessions with a completion banner and the existing list', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'synced_with_sessions',
      result: {
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
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴を最新化しました' })).toBeInTheDocument()
    expect(screen.getByText('3 件を保存しました。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  it('renders a synced-empty banner and keeps the empty state distinct from failure', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
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
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴の同期は完了しました' })).toBeInTheDocument()
    expect(screen.getByText('取り込みは完了しましたが、表示できるセッションはまだありません。')).toBeInTheDocument()
    expect(screen.getByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '履歴を取り込む' })).toBeInTheDocument()
  })

  it.each([
    {
      name: 'refresh error',
      syncState: {
        status: 'refresh_error',
        result: {
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
        error: {
          kind: 'backend',
          httpStatus: 503,
          code: 'root_missing',
          message: 'history root does not exist',
          details: { path: '/tmp/.copilot' },
        },
      } satisfies HistorySyncState,
      heading: '履歴の同期は完了しましたが、最新の一覧を表示できません',
    },
    {
      name: 'conflict',
      syncState: {
        status: 'conflict',
        error: {
          kind: 'backend',
          httpStatus: 409,
          code: 'history_sync_running',
          message: 'history sync is already running',
          details: { sync_run_id: 7 },
        },
      } satisfies HistorySyncState,
      heading: '履歴同期はすでに進行中の可能性があります',
    },
    {
      name: 'sync error',
      syncState: {
        status: 'sync_error',
        error: {
          kind: 'network',
          code: 'network_error',
          message: 'Network request failed',
          details: { cause: 'Failed to fetch' },
        },
      } satisfies HistorySyncState,
      heading: '履歴を同期できませんでした',
    },
  ])('renders the %s banner without hiding the current list', ({ syncState, heading }) => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult(syncState))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  it('keeps the existing session list visible while a sync is in progress', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({ status: 'syncing' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  it('shows sync failures separately from the initial index error state', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 503,
        code: 'root_missing',
        message: 'history root does not exist',
        details: {
          path: '/tmp/.copilot',
        },
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'sync_error',
      error: {
        kind: 'backend',
        httpStatus: 500,
        code: 'history_sync_failed',
        message: 'history sync failed',
        details: {},
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴を同期できませんでした' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を表示できません' })).toBeInTheDocument()
  })
})

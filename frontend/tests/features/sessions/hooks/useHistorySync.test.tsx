import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { createRef, forwardRef, StrictMode, useImperativeHandle, type RefObject } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  HistorySyncResponse,
  SessionApiClient,
  SessionApiError,
  SessionApiResult,
  SessionDetailResponse,
  SessionIndexResponse,
  SessionSummary,
} from '../../../../src/features/sessions/api/sessionApi.types.ts'
import { useHistorySync } from '../../../../src/features/sessions/hooks/useHistorySync.ts'
import type { SessionIndexSettledState } from '../../../../src/features/sessions/hooks/useSessionIndex.ts'

function deferred<T>() {
  let resolve!: (value: T) => void

  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })

  return { promise, resolve }
}

function createClient(syncHistory: SessionApiClient['syncHistory']): SessionApiClient {
  return {
    fetchSessionIndex: vi.fn<
      SessionApiClient['fetchSessionIndex']
    >(async (): Promise<SessionApiResult<SessionIndexResponse>> => {
      throw new Error('fetchSessionIndex should not be called in useHistorySync tests')
    }),
    fetchSessionDetail: vi.fn<
      SessionApiClient['fetchSessionDetail']
    >(async (): Promise<SessionApiResult<SessionDetailResponse>> => {
      throw new Error('fetchSessionDetail should not be called in useHistorySync tests')
    }),
    fetchSessionDetailWithRaw: vi.fn<
      SessionApiClient['fetchSessionDetailWithRaw']
    >(async (): Promise<SessionApiResult<SessionDetailResponse>> => {
      throw new Error('fetchSessionDetailWithRaw should not be called in useHistorySync tests')
    }),
    syncHistory,
  }
}

const StateProbe = forwardRef<
  ReturnType<typeof useHistorySync>,
  {
    client: SessionApiClient
    reloadSessions: () => Promise<SessionIndexSettledState>
  }
>(function StateProbe({ client, reloadSessions }, ref) {
  const hookResult = useHistorySync({ client, reloadSessions })

  useImperativeHandle(ref, () => hookResult, [hookResult])

  return (
    <>
      <pre data-testid="state">{JSON.stringify(hookResult.state)}</pre>
      <pre data-testid="syncing">{JSON.stringify(hookResult.isSyncing)}</pre>
    </>
  )
})

function readState() {
  return JSON.parse(screen.getByTestId('state').textContent ?? 'null')
}

function readIsSyncing() {
  return JSON.parse(screen.getByTestId('syncing').textContent ?? 'false')
}

function renderStateProbe(
  client: SessionApiClient,
  reloadSessions: () => Promise<SessionIndexSettledState>,
  options: {
    strictMode?: boolean
  } = {},
) {
  const ref = createRef<ReturnType<typeof useHistorySync>>()
  const probe = <StateProbe client={client} reloadSessions={reloadSessions} ref={ref} />
  const view = render(options.strictMode ? <StrictMode>{probe}</StrictMode> : probe)

  return { ref, ...view }
}

function startSync(ref: RefObject<ReturnType<typeof useHistorySync> | null>) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.startSync()
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

function buildSyncPayload(): HistorySyncResponse {
  return {
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
        degraded_count: 1,
      },
    },
  }
}

function buildReloadSuccessState(): SessionIndexSettledState {
  return {
    status: 'success',
    sessions: [buildSessionSummary()],
    meta: {
      count: 1,
      partial_results: false,
    },
  }
}

afterEach(() => {
  cleanup()
})

describe('useHistorySync', () => {
  /**
   * 概要・目的: 「starts idle and does not issue a sync request until explicitly started」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「starts idle and does not issue a sync request until explicitly started」の条件・入力・操作を実行する。
   * 期待値: 「starts idle and does not issue a sync request until explicitly started」で示す状態または振る舞いが成立すること。
   */
  it('starts idle and does not issue a sync request until explicitly started', () => {
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(async () => ({
      status: 'success',
      data: buildSyncPayload(),
    }))
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => buildReloadSuccessState(),
    )
    const client = createClient(syncHistory)

    renderStateProbe(client, reloadSessions)

    expect(readState()).toEqual({ status: 'idle' })
    expect(readIsSyncing()).toBe(false)
    expect(syncHistory).not.toHaveBeenCalled()
    expect(reloadSessions).not.toHaveBeenCalled()
  })

  /**
   * 概要・目的: 「suppresses duplicate starts while syncing and issues a new request after a terminal retry」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「suppresses duplicate starts while syncing and issues a new request after a terminal
   *   retry」の条件・入力・操作を実行する。
   * 期待値: duplicate starts while syncing and issues a new request after a terminal retry が抑止されること。
   */
  it('suppresses duplicate starts while syncing and issues a new request after a terminal retry', async () => {
    const firstRequest = deferred<SessionApiResult<HistorySyncResponse>>()
    const secondRequest = deferred<SessionApiResult<HistorySyncResponse>>()
    const syncHistory = vi
      .fn<SessionApiClient['syncHistory']>()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => ({ status: 'empty' } as const),
    )
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions)

    let firstStart!: Promise<void>
    let duplicateStart!: Promise<void>
    act(() => {
      firstStart = startSync(ref)
      duplicateStart = startSync(ref)
    })

    expect(duplicateStart).toBe(firstStart)
    expect(syncHistory).toHaveBeenCalledTimes(1)
    expect(readState()).toEqual({ status: 'syncing' })
    expect(readIsSyncing()).toBe(true)

    await act(async () => {
      firstRequest.resolve({
        status: 'error',
        error: {
          kind: 'network',
          code: 'network_error',
          message: 'Network request failed',
          details: {
            cause: 'Failed to fetch',
          },
        },
      })

      await firstStart
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'sync_error',
        error: {
          kind: 'network',
          code: 'network_error',
          message: 'Network request failed',
          details: {
            cause: 'Failed to fetch',
          },
        },
      }),
    )
    expect(readIsSyncing()).toBe(false)
    expect(reloadSessions).not.toHaveBeenCalled()

    let retryStart!: Promise<void>
    act(() => {
      retryStart = startSync(ref)
    })

    expect(syncHistory).toHaveBeenCalledTimes(2)
    expect(readState()).toEqual({ status: 'syncing' })

    await act(async () => {
      secondRequest.resolve({
        status: 'success',
        data: buildSyncPayload(),
      })

      await retryStart
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'synced_empty',
        result: buildSyncPayload().data,
      }),
    )
    expect(reloadSessions).toHaveBeenCalledTimes(1)
  })

  /**
   * 概要・目的: 「transitions to synced_with_sessions after a successful sync and a successful
   *   reload」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「transitions to synced_with_sessions after a successful sync and a successful
   *   reload」の条件・入力・操作を実行する。
   * 期待値: 状態が synced_with_sessions after a successful sync and a successful reload に遷移すること。
   */
  it('transitions to synced_with_sessions after a successful sync and a successful reload', async () => {
    const syncPayload = buildSyncPayload()
    const syncRequest = deferred<SessionApiResult<HistorySyncResponse>>()
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(() => syncRequest.promise)
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => buildReloadSuccessState(),
    )
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions)

    let startPromise!: Promise<void>
    act(() => {
      startPromise = startSync(ref)
    })

    expect(reloadSessions).not.toHaveBeenCalled()

    await act(async () => {
      syncRequest.resolve({
        status: 'success',
        data: syncPayload,
      })

      await startPromise
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'synced_with_sessions',
        result: syncPayload.data,
      }),
    )
    expect(reloadSessions).toHaveBeenCalledTimes(1)
    expect(syncHistory.mock.invocationCallOrder[0]).toBeLessThan(
      reloadSessions.mock.invocationCallOrder[0],
    )
  })

  /**
   * 概要・目的: 「restores mounted state after StrictMode effect replays so sync state still updates」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「restores mounted state after StrictMode effect replays so sync state still
   *   updates」の条件・入力・操作を実行する。
   * 期待値: mounted state after StrictMode effect replays so sync state still updates が復元されること。
   */
  it('restores mounted state after StrictMode effect replays so sync state still updates', async () => {
    const syncPayload = buildSyncPayload()
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(async () => ({
      status: 'success',
      data: syncPayload,
    }))
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => buildReloadSuccessState(),
    )
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions, { strictMode: true })

    await act(async () => {
      await startSync(ref)
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'synced_with_sessions',
        result: syncPayload.data,
      }),
    )
    expect(readIsSyncing()).toBe(false)
    expect(syncHistory).toHaveBeenCalledTimes(1)
    expect(reloadSessions).toHaveBeenCalledTimes(1)
  })

  /**
   * 概要・目的: 「transitions to refresh_error when sync succeeds but reload fails」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「transitions to refresh_error when sync succeeds but reload fails」の条件・入力・操作を実行する。
   * 期待値: 状態が refresh_error when sync succeeds but reload fails に遷移すること。
   */
  it('transitions to refresh_error when sync succeeds but reload fails', async () => {
    const syncPayload = buildSyncPayload()
    const reloadError: SessionApiError = {
      kind: 'backend',
      httpStatus: 503,
      code: 'root_missing',
      message: 'history root does not exist',
      details: {
        path: '/tmp/.copilot',
      },
    }
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(async () => ({
      status: 'success',
      data: syncPayload,
    }))
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(async () => ({
      status: 'error',
      error: reloadError,
    }))
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions)

    await act(async () => {
      await startSync(ref)
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'refresh_error',
        result: syncPayload.data,
        error: reloadError,
      }),
    )
    expect(reloadSessions).toHaveBeenCalledTimes(1)
  })

  /**
   * 概要・目的: 「classifies a history_sync_running conflict separately from other sync
   *   failures」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「classifies a history_sync_running conflict separately from other sync failures」の条件・入力・操作を実行する。
   * 期待値: 「classifies a history_sync_running conflict separately from other sync failures」で示す状態または振る舞いが成立すること。
   */
  it('classifies a history_sync_running conflict separately from other sync failures', async () => {
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(async () => ({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 409,
        code: 'history_sync_running',
        message: 'history sync is already running',
        details: {
          sync_run_id: 7,
        },
      },
    }))
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => buildReloadSuccessState(),
    )
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions)

    await act(async () => {
      await startSync(ref)
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'conflict',
        error: {
          kind: 'backend',
          httpStatus: 409,
          code: 'history_sync_running',
          message: 'history sync is already running',
          details: {
            sync_run_id: 7,
          },
        },
      }),
    )
    expect(reloadSessions).not.toHaveBeenCalled()
  })

  /**
   * 概要・目的: 「classifies $label as sync_error」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「classifies $label as sync_error」の条件・入力・操作を実行する。
   * 期待値: $label が sync_error として分類されること。
   */
  it.each([
    {
      label: 'backend failures',
      error: {
        kind: 'backend',
        httpStatus: 500,
        code: 'history_sync_failed',
        message: 'history sync failed',
        details: {
          sync_run_id: 8,
        },
      } satisfies SessionApiError,
    },
    {
      label: 'network failures',
      error: {
        kind: 'network',
        code: 'network_error',
        message: 'Network request failed',
        details: {
          cause: 'Failed to fetch',
        },
      } satisfies SessionApiError,
    },
    {
      label: 'config failures',
      error: {
        kind: 'config',
        code: 'api_base_url_missing',
        message: 'VITE_API_BASE_URL is not configured',
        details: {
          env: 'VITE_API_BASE_URL',
        },
      } satisfies SessionApiError,
    },
  ])('classifies $label as sync_error', async ({ error }) => {
    const syncHistory = vi.fn<SessionApiClient['syncHistory']>(async () => ({
      status: 'error',
      error,
    }))
    const reloadSessions = vi.fn<() => Promise<SessionIndexSettledState>>(
      async () => buildReloadSuccessState(),
    )
    const client = createClient(syncHistory)
    const { ref } = renderStateProbe(client, reloadSessions)

    await act(async () => {
      await startSync(ref)
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'sync_error',
        error,
      }),
    )
    expect(reloadSessions).not.toHaveBeenCalled()
  })
})

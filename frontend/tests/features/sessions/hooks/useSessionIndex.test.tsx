import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { createRef, forwardRef, useImperativeHandle, type RefObject } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  SessionApiClient,
  SessionApiResult,
  SessionDetailResponse,
  SessionIndexResponse,
} from '../../../../src/features/sessions/api/sessionApi.types.ts'
import { useSessionIndex } from '../../../../src/features/sessions/hooks/useSessionIndex.ts'

const DEFAULT_RANGE = {
  from: '2026-04-28',
  to: '2026-05-04',
} as const

const DEFAULT_QUERY = {
  from: '2026-04-28T00:00:00+09:00',
  to: '2026-05-04T23:59:59.999999+09:00',
} as const
const FIXED_NOW = () => new Date('2026-05-03T18:15:00Z')

function deferred<T>() {
  let resolve!: (value: T) => void

  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })

  return { promise, resolve }
}

function createClient(fetchSessionIndex: SessionApiClient['fetchSessionIndex']): SessionApiClient {
  return {
    fetchSessionIndex,
    fetchSessionDetail: vi.fn<
      SessionApiClient['fetchSessionDetail']
    >(async (): Promise<SessionApiResult<SessionDetailResponse>> => {
      throw new Error('fetchSessionDetail should not be called in useSessionIndex tests')
    }),
    fetchSessionDetailWithRaw: vi.fn<
      SessionApiClient['fetchSessionDetailWithRaw']
    >(async (): Promise<SessionApiResult<SessionDetailResponse>> => {
      throw new Error('fetchSessionDetailWithRaw should not be called in useSessionIndex tests')
    }),
    syncHistory: vi.fn<SessionApiClient['syncHistory']>(async () => {
      throw new Error('syncHistory should not be called in useSessionIndex tests')
    }),
  }
}

const StateProbe = forwardRef<
  ReturnType<typeof useSessionIndex>,
  {
    client: SessionApiClient
    now?: () => Date
  }
>(function StateProbe({ client, now = FIXED_NOW }, ref) {
  const hookResult = useSessionIndex({ client, now })

  useImperativeHandle(ref, () => hookResult, [hookResult])

  return (
    <>
      <pre data-testid="state">{JSON.stringify(hookResult.state)}</pre>
      <pre data-testid="range">{JSON.stringify(hookResult.appliedRange)}</pre>
      <pre data-testid="search">{JSON.stringify(hookResult.appliedSearchTerm)}</pre>
      <pre data-testid="refreshing">{JSON.stringify(hookResult.isRefreshing)}</pre>
    </>
  )
})

function readState() {
  return JSON.parse(screen.getByTestId('state').textContent ?? 'null')
}

function readAppliedRange() {
  return JSON.parse(screen.getByTestId('range').textContent ?? 'null')
}

function readRefreshing() {
  return JSON.parse(screen.getByTestId('refreshing').textContent ?? 'false')
}

function readAppliedSearchTerm() {
  return JSON.parse(screen.getByTestId('search').textContent ?? '""')
}

function renderStateProbe(client: SessionApiClient, now?: () => Date) {
  const ref = createRef<ReturnType<typeof useSessionIndex>>()
  const view = render(<StateProbe client={client} now={now} ref={ref} />)

  return { ref, ...view }
}

function reloadSessions(ref: RefObject<ReturnType<typeof useSessionIndex> | null>) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.reloadSessions()
}

function applyRange(
  ref: RefObject<ReturnType<typeof useSessionIndex> | null>,
  range: { from: string; to: string },
) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.applyRange(range)
}

function applySearch(
  ref: RefObject<ReturnType<typeof useSessionIndex> | null>,
  searchTerm: string,
) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.applySearch(searchTerm)
}

function clearSearch(ref: RefObject<ReturnType<typeof useSessionIndex> | null>) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.clearSearch()
}

function buildIndexResponse(
  data: SessionIndexResponse['data'] = [
    {
      id: 'session-b',
      source_format: 'current',
      created_at: '2026-04-26T10:00:00Z',
      updated_at: '2026-04-26T10:05:00Z',
      work_context: {
        cwd: '/workspace/session-b',
        git_root: '/workspace/session-b',
        repository: 'octo/example',
        branch: 'feature/b',
      },
      selected_model: 'gpt-5.4',
      source_state: 'complete',
      event_count: 3,
      message_snapshot_count: 1,
      conversation_summary: {
        has_conversation: true,
        message_count: 1,
        preview: 'current transcript',
        activity_count: 2,
      },
      degraded: false,
      issues: [],
    },
  ],
): SessionIndexResponse {
  return {
    data,
    meta: {
      count: data.length,
      partial_results: false,
    },
  }
}

afterEach(() => {
  cleanup()
})

describe('useSessionIndex', () => {
  /**
   * 概要・目的: 「loads the default 7-day range on mount and exposes it as the applied range」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「loads the default 7-day range on mount and exposes it as the applied range」の条件・入力・操作を実行する。
   * 期待値: the default 7-day range on mount and exposes it as the applied range が読み込まれること。
   */
  it('loads the default 7-day range on mount and exposes it as the applied range', async () => {
    const payload = buildIndexResponse()
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>(async () => ({
      status: 'success',
      data: payload,
    }))
    const client = createClient(fetchSessionIndex)

    renderStateProbe(client)

    expect(readState()).toEqual({ status: 'loading' })
    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: payload.data,
        meta: payload.meta,
      }),
    )

    expect(fetchSessionIndex).toHaveBeenCalledWith(
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「captures the initial default range from now() only once during startup」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「captures the initial default range from now() only once during startup」の条件・入力・操作を実行する。
   * 期待値: the initial default range from now() only once during startup が保持されること。
   */
  it('captures the initial default range from now() only once during startup', async () => {
    const payload = buildIndexResponse()
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>(async () => ({
      status: 'success',
      data: payload,
    }))
    const client = createClient(fetchSessionIndex)
    const now = vi
      .fn<() => Date>()
      .mockReturnValueOnce(new Date('2026-05-03T14:59:59Z'))
      .mockReturnValue(new Date('2026-05-03T15:00:00Z'))

    render(<StateProbe client={client} now={now} />)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: payload.data,
        meta: payload.meta,
      }),
    )

    expect(now).toHaveBeenCalledTimes(1)
    expect(readAppliedRange()).toEqual({
      from: '2026-04-27',
      to: '2026-05-03',
    })
    expect(fetchSessionIndex).toHaveBeenCalledWith(
      expect.objectContaining({
        query: {
          from: '2026-04-27T00:00:00+09:00',
          to: '2026-05-03T23:59:59.999999+09:00',
        },
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「reuses only the same-query snapshot immediately on remount」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「reuses only the same-query snapshot immediately on remount」の条件・入力・操作を実行する。
   * 期待値: 「reuses only the same-query snapshot immediately on remount」で示す状態または振る舞いが成立すること。
   */
  it('reuses only the same-query snapshot immediately on remount', async () => {
    const firstPayload = buildIndexResponse()
    const nextRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: firstPayload })
      .mockReturnValueOnce(nextRequest.promise)
    const client = createClient(fetchSessionIndex)

    const firstRender = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: firstPayload.data,
        meta: firstPayload.meta,
      }),
    )

    firstRender.unmount()
    renderStateProbe(client)

    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readState()).toEqual({
      status: 'success',
      sessions: firstPayload.data,
      meta: firstPayload.meta,
    })
    expect(fetchSessionIndex).toHaveBeenCalledTimes(2)
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「surfaces a remount revalidation error instead of silently keeping a stale snapshot」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「surfaces a remount revalidation error instead of silently keeping a stale
   *   snapshot」の条件・入力・操作を実行する。
   * 期待値: 「surfaces a remount revalidation error instead of silently keeping a stale
   *   snapshot」で示す状態または振る舞いが成立すること。
   */
  it('surfaces a remount revalidation error instead of silently keeping a stale snapshot', async () => {
    const payload = buildIndexResponse()
    const revalidationError = {
      status: 'error' as const,
      error: {
        kind: 'network' as const,
        code: 'network_error' as const,
        message: 'network unavailable',
        details: {
          cause: 'offline',
        },
      },
    }
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: payload })
      .mockResolvedValueOnce(revalidationError)
    const client = createClient(fetchSessionIndex)

    const firstRender = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: payload.data,
        meta: payload.meta,
      }),
    )

    firstRender.unmount()
    renderStateProbe(client)

    expect(readState()).toEqual({
      status: 'success',
      sessions: payload.data,
      meta: payload.meta,
    })

    await waitFor(() => expect(readState()).toEqual(revalidationError))
  })

  /**
   * 概要・目的: 「treats an apply for a different range as a new loading state instead of keeping the old success
   *   visible」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「treats an apply for a different range as a new loading state instead of keeping the old success
   *   visible」の条件・入力・操作を実行する。
   * 期待値: an apply for a different range が a new loading state instead of keeping the old success visible
   *   として扱われること。
   */
  it('treats an apply for a different range as a new loading state instead of keeping the old success visible', async () => {
    const initialPayload = buildIndexResponse()
    const nextPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-next',
        updated_at: '2026-05-01T01:00:00Z',
      },
    ])
    const applyRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(applyRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    const nextRange = {
      from: '2026-05-01',
      to: '2026-05-07',
    }

    let applyPromise!: Promise<unknown>
    await act(async () => {
      applyPromise = applyRange(ref, nextRange)
    })

    expect(readAppliedRange()).toEqual(nextRange)
    expect(readState()).toEqual({ status: 'loading' })

    await act(async () => {
      applyRequest.resolve({ status: 'success', data: nextPayload })

      await expect(applyPromise).resolves.toEqual({
        status: 'success',
        sessions: nextPayload.data,
        meta: nextPayload.meta,
      })
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: nextPayload.data,
        meta: nextPayload.meta,
      }),
    )

    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: {
          from: '2026-05-01T00:00:00+09:00',
          to: '2026-05-07T23:59:59.999999+09:00',
        },
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「resolves an empty apply back to the explicit default 7-day range」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「resolves an empty apply back to the explicit default 7-day range」の条件・入力・操作を実行する。
   * 期待値: 「resolves an empty apply back to the explicit default 7-day range」で示す状態または振る舞いが成立すること。
   */
  it('resolves an empty apply back to the explicit default 7-day range', async () => {
    const defaultPayload = buildIndexResponse()
    const selectedPayload = buildIndexResponse([
      {
        ...defaultPayload.data[0],
        id: 'session-filtered',
      },
    ])
    const resetPayload = buildIndexResponse([])
    const selectRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const resetRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: defaultPayload })
      .mockReturnValueOnce(selectRequest.promise)
      .mockReturnValueOnce(resetRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: defaultPayload.data,
        meta: defaultPayload.meta,
      }),
    )

    await act(async () => {
      const applyPromise = applyRange(ref, {
        from: '2026-05-01',
        to: '2026-05-07',
      })

      selectRequest.resolve({ status: 'success', data: selectedPayload })
      await applyPromise
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: selectedPayload.data,
        meta: selectedPayload.meta,
      }),
    )

    let resetPromise!: Promise<unknown>
    await act(async () => {
      resetPromise = applyRange(ref, { from: '', to: '' })
    })

    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readState()).toEqual({ status: 'loading' })

    await act(async () => {
      resetRequest.resolve({ status: 'success', data: resetPayload })
      await expect(resetPromise).resolves.toEqual({ status: 'empty' })
    })

    await waitFor(() => expect(readState()).toEqual({ status: 'empty' }))
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「keeps the attempted range when a different-range apply fails」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「keeps the attempted range when a different-range apply fails」の条件・入力・操作を実行する。
   * 期待値: the attempted range when a different-range apply fails が維持されること。
   */
  it('keeps the attempted range when a different-range apply fails', async () => {
    const initialPayload = buildIndexResponse()
    const applyError = {
      status: 'error' as const,
      error: {
        kind: 'backend' as const,
        httpStatus: 503,
        code: 'root_missing',
        message: 'history root does not exist',
        details: {
          path: '/tmp/.copilot',
        },
      },
    }
    const applyRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(applyRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    const attemptedRange = {
      from: '2026-05-10',
      to: '',
    }

    let applyPromise!: Promise<unknown>
    await act(async () => {
      applyPromise = applyRange(ref, attemptedRange)
    })

    expect(readAppliedRange()).toEqual(attemptedRange)
    expect(readState()).toEqual({ status: 'loading' })

    await act(async () => {
      applyRequest.resolve(applyError)
      await expect(applyPromise).resolves.toEqual(applyError)
    })

    await waitFor(() => expect(readState()).toEqual(applyError))
    expect(readAppliedRange()).toEqual(attemptedRange)
  })

  /**
   * 概要・目的: 「preserves the previous same-range snapshot while reload is in flight」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「preserves the previous same-range snapshot while reload is in flight」の条件・入力・操作を実行する。
   * 期待値: the previous same-range snapshot while reload is in flight が保持されること。
   */
  it('preserves the previous same-range snapshot while reload is in flight', async () => {
    const initialPayload = buildIndexResponse()
    const refreshedPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-refreshed',
      },
    ])
    const reloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(reloadRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    let reloadPromise!: Promise<unknown>
    await act(async () => {
      reloadPromise = reloadSessions(ref)
    })

    expect(readRefreshing()).toBe(true)
    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readState()).toEqual({
      status: 'success',
      sessions: initialPayload.data,
      meta: initialPayload.meta,
    })

    await act(async () => {
      reloadRequest.resolve({ status: 'success', data: refreshedPayload })

      await expect(reloadPromise).resolves.toEqual({
        status: 'success',
        sessions: refreshedPayload.data,
        meta: refreshedPayload.meta,
      })
    })

    await waitFor(() => expect(readRefreshing()).toBe(false))
    expect(readState()).toEqual({
      status: 'success',
      sessions: refreshedPayload.data,
      meta: refreshedPayload.meta,
    })
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「reads the latest applied range during reload even when the callback was captured
   *   earlier」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「reads the latest applied range during reload even when the callback was captured
   *   earlier」の条件・入力・操作を実行する。
   * 期待値: the latest applied range during reload even when the callback was captured earlier が読み取られること。
   */
  it('reads the latest applied range during reload even when the callback was captured earlier', async () => {
    const initialPayload = buildIndexResponse()
    const appliedPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-applied',
      },
    ])
    const refreshedPayload = buildIndexResponse([
      {
        ...appliedPayload.data[0],
        id: 'session-after-sync',
      },
    ])
    const applyRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const reloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(applyRequest.promise)
      .mockReturnValueOnce(reloadRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    if (ref.current == null) {
      throw new Error('Hook result is not available yet')
    }

    const staleReload = ref.current.reloadSessions

    await act(async () => {
      const applyPromise = applyRange(ref, {
        from: '',
        to: '2026-05-02',
      })

      applyRequest.resolve({ status: 'success', data: appliedPayload })
      await applyPromise
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: appliedPayload.data,
        meta: appliedPayload.meta,
      }),
    )

    let reloadPromise!: Promise<unknown>
    await act(async () => {
      reloadPromise = staleReload()
    })

    await act(async () => {
      reloadRequest.resolve({ status: 'success', data: refreshedPayload })
      await expect(reloadPromise).resolves.toEqual({
        status: 'success',
        sessions: refreshedPayload.data,
        meta: refreshedPayload.meta,
      })
    })

    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: {
          to: '2026-05-02T23:59:59.999999+09:00',
        },
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「ignores stale apply responses and keeps the latest range result visible」を通じて、HTTP
   *   レスポンスとエラー契約を検証する。
   * テストケース: 「ignores stale apply responses and keeps the latest range result visible」の条件・入力・操作を実行する。
   * 期待値: stale apply responses and keeps the latest range result visible が無視されること。
   */
  it('ignores stale apply responses and keeps the latest range result visible', async () => {
    const initialPayload = buildIndexResponse()
    const staleApplyRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const latestApplyRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const latestPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-latest',
      },
    ])
    const stalePayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-stale',
      },
    ])
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(staleApplyRequest.promise)
      .mockReturnValueOnce(latestApplyRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    let staleApplyPromise!: Promise<unknown>
    let latestApplyPromise!: Promise<unknown>
    await act(async () => {
      staleApplyPromise = applyRange(ref, {
        from: '2026-05-01',
        to: '2026-05-03',
      })
      latestApplyPromise = applyRange(ref, {
        from: '2026-05-05',
        to: '2026-05-07',
      })
    })

    await act(async () => {
      latestApplyRequest.resolve({ status: 'success', data: latestPayload })
      await expect(latestApplyPromise).resolves.toEqual({
        status: 'success',
        sessions: latestPayload.data,
        meta: latestPayload.meta,
      })
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: latestPayload.data,
        meta: latestPayload.meta,
      }),
    )

    await act(async () => {
      staleApplyRequest.resolve({ status: 'success', data: stalePayload })
      await staleApplyPromise
    })

    expect(readAppliedRange()).toEqual({
      from: '2026-05-05',
      to: '2026-05-07',
    })
    expect(readState()).toEqual({
      status: 'success',
      sessions: latestPayload.data,
      meta: latestPayload.meta,
    })
  })

  /**
   * 概要・目的: 「applies a search term while preserving the current date range」を通じて、reader と fixture
   *   の読取・劣化時の扱いを検証する。
   * テストケース: 「applies a search term while preserving the current date range」の条件・入力・操作を実行する。
   * 期待値: a search term while preserving the current date range が適用されること。
   */
  it('applies a search term while preserving the current date range', async () => {
    const initialPayload = buildIndexResponse()
    const searchPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'search-result',
      },
    ])
    const searchRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(searchRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    let searchPromise!: Promise<unknown>
    await act(async () => {
      searchPromise = applySearch(ref, '  apply   patch  ')
    })

    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readAppliedSearchTerm()).toBe('apply patch')
    expect(readState()).toEqual({ status: 'loading' })

    await act(async () => {
      searchRequest.resolve({ status: 'success', data: searchPayload })
      await expect(searchPromise).resolves.toEqual({
        status: 'success',
        sessions: searchPayload.data,
        meta: searchPayload.meta,
      })
    })

    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: {
          ...DEFAULT_QUERY,
          search: 'apply patch',
        },
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: 「clears the search term while preserving the current date range」を通じて、reader と fixture
   *   の読取・劣化時の扱いを検証する。
   * テストケース: 「clears the search term while preserving the current date range」の条件・入力・操作を実行する。
   * 期待値: 「clears the search term while preserving the current date range」で示す状態または振る舞いが成立すること。
   */
  it('clears the search term while preserving the current date range', async () => {
    const initialPayload = buildIndexResponse()
    const searchPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'search-result' }])
    const clearedPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'cleared-result' }])
    const searchRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const clearRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(searchRequest.promise)
      .mockReturnValueOnce(clearRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() => expect(readState().status).toBe('success'))

    await act(async () => {
      const searchPromise = applySearch(ref, 'issue message')
      searchRequest.resolve({ status: 'success', data: searchPayload })
      await searchPromise
    })

    let clearPromise!: Promise<unknown>
    await act(async () => {
      clearPromise = clearSearch(ref)
    })

    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readAppliedSearchTerm()).toBe('')
    expect(readState()).toEqual({ status: 'loading' })

    await act(async () => {
      clearRequest.resolve({ status: 'success', data: clearedPayload })
      await clearPromise
    })

    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
  })

  /**
   * 概要・目的: cwd 由来のパス断片検索を適用・解除しても、現在の日付範囲を同じ一覧条件として維持する契約を検証する。
   * テストケース: 実行ディレクトリの一部にあたる検索語を適用し、その後検索語を解除する。
   * 期待値: 検索適用時も解除時も既存の日付範囲が API query に残り、検索語だけが追加・削除されること。
   */
  it('applies and clears a cwd path fragment while preserving the current date range', async () => {
    const initialPayload = buildIndexResponse()
    const cwdSearchPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'cwd-search-result' }])
    const clearedPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'cwd-cleared-result' }])
    const searchRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const clearRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(searchRequest.promise)
      .mockReturnValueOnce(clearRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() => expect(readState().status).toBe('success'))

    await act(async () => {
      const searchPromise = applySearch(ref, ' /workspace/copilot-cli-history ')
      searchRequest.resolve({ status: 'success', data: cwdSearchPayload })
      await searchPromise
    })

    await act(async () => {
      const clearPromise = clearSearch(ref)
      clearRequest.resolve({ status: 'success', data: clearedPayload })
      await clearPromise
    })

    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        query: {
          ...DEFAULT_QUERY,
          search: '/workspace/copilot-cli-history',
        },
        signal: expect.any(AbortSignal),
      }),
    )
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: DEFAULT_QUERY,
        signal: expect.any(AbortSignal),
      }),
    )
    expect(readAppliedRange()).toEqual(DEFAULT_RANGE)
    expect(readAppliedSearchTerm()).toBe('')
  })

  /**
   * 概要・目的: 「preserves search while applying a new date range and while reloading after
   *   sync」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「preserves search while applying a new date range and while reloading after sync」の条件・入力・操作を実行する。
   * 期待値: search while applying a new date range が保持され、while reloading after syncこと。
   */
  it('preserves search while applying a new date range and while reloading after sync', async () => {
    const initialPayload = buildIndexResponse()
    const searchPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'search-result' }])
    const rangePayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'range-result' }])
    const reloadPayload = buildIndexResponse([{ ...initialPayload.data[0], id: 'reload-result' }])
    const searchRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const rangeRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const reloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(searchRequest.promise)
      .mockReturnValueOnce(rangeRequest.promise)
      .mockReturnValueOnce(reloadRequest.promise)
    const client = createClient(fetchSessionIndex)
    const { ref } = renderStateProbe(client)

    await waitFor(() => expect(readState().status).toBe('success'))

    await act(async () => {
      const searchPromise = applySearch(ref, 'gpt-5')
      searchRequest.resolve({ status: 'success', data: searchPayload })
      await searchPromise
    })

    await act(async () => {
      const rangePromise = applyRange(ref, { from: '2026-05-01', to: '2026-05-07' })
      rangeRequest.resolve({ status: 'success', data: rangePayload })
      await rangePromise
    })

    await act(async () => {
      const reloadPromise = reloadSessions(ref)
      reloadRequest.resolve({ status: 'success', data: reloadPayload })
      await reloadPromise
    })

    expect(readAppliedSearchTerm()).toBe('gpt-5')
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        query: {
          from: '2026-05-01T00:00:00+09:00',
          to: '2026-05-07T23:59:59.999999+09:00',
          search: 'gpt-5',
        },
        signal: expect.any(AbortSignal),
      }),
    )
    expect(fetchSessionIndex).toHaveBeenNthCalledWith(
      4,
      expect.objectContaining({
        query: {
          from: '2026-05-01T00:00:00+09:00',
          to: '2026-05-07T23:59:59.999999+09:00',
          search: 'gpt-5',
        },
        signal: expect.any(AbortSignal),
      }),
    )
  })
})

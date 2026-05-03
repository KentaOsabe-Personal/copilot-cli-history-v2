import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { createRef, forwardRef, useImperativeHandle, type RefObject } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  SessionApiClient,
  SessionApiResult,
  SessionDetailResponse,
  SessionIndexResponse,
} from '../api/sessionApi.types.ts'
import { useSessionIndex } from './useSessionIndex.ts'

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
  { client: SessionApiClient }
>(function StateProbe({ client }, ref) {
  const hookResult = useSessionIndex({ client })

  useImperativeHandle(ref, () => hookResult, [hookResult])

  return (
    <>
      <pre data-testid="state">{JSON.stringify(hookResult.state)}</pre>
      <pre data-testid="refreshing">{JSON.stringify(hookResult.isRefreshing)}</pre>
    </>
  )
})

function readState() {
  return JSON.parse(screen.getByTestId('state').textContent ?? 'null')
}

function readRefreshing() {
  return JSON.parse(screen.getByTestId('refreshing').textContent ?? 'false')
}

function renderStateProbe(client: SessionApiClient) {
  const ref = createRef<ReturnType<typeof useSessionIndex>>()
  const view = render(<StateProbe client={client} ref={ref} />)

  return { ref, ...view }
}

function reloadSessions(ref: RefObject<ReturnType<typeof useSessionIndex> | null>) {
  if (ref.current == null) {
    throw new Error('Hook result is not available yet')
  }

  return ref.current.reloadSessions()
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
  it('starts in loading and transitions to success without reordering sessions', async () => {
    const request = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>(() => request.promise)
    const client = createClient(fetchSessionIndex)

    renderStateProbe(client)

    expect(readState()).toEqual({ status: 'loading' })

    const payload: SessionIndexResponse = {
      data: [
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
        {
          id: 'session-a',
          source_format: 'legacy',
          created_at: '2026-04-26T08:00:00Z',
          updated_at: null,
          work_context: {
            cwd: null,
            git_root: null,
            repository: null,
            branch: null,
          },
          selected_model: null,
          source_state: 'degraded',
          event_count: 1,
          message_snapshot_count: 0,
          conversation_summary: {
            has_conversation: false,
            message_count: 0,
            preview: null,
            activity_count: 1,
          },
          degraded: true,
          issues: [],
        },
      ],
      meta: {
        count: 2,
        partial_results: true,
      },
    }

    request.resolve({ status: 'success', data: payload })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: payload.data,
        meta: payload.meta,
      }),
    )
    expect(fetchSessionIndex).toHaveBeenCalledTimes(1)
  })

  it('separates an empty response from success', async () => {
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>(async () => ({
      status: 'success',
      data: {
        data: [],
        meta: {
          count: 0,
          partial_results: false,
        },
      },
    }))
    const client = createClient(fetchSessionIndex)

    renderStateProbe(client)

    await waitFor(() => expect(readState()).toEqual({ status: 'empty' }))
  })

  it('exposes backend and network/config failures as an error state', async () => {
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>(async () => ({
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
    const client = createClient(fetchSessionIndex)

    renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
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
      }),
    )
  })

  it('aborts the in-flight request when the hook unmounts', () => {
    let observedSignal: AbortSignal | undefined
    const pendingRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi.fn<SessionApiClient['fetchSessionIndex']>((request) => {
      observedSignal = request?.signal

      return pendingRequest.promise
    })
    const client = createClient(fetchSessionIndex)

    const { unmount } = renderStateProbe(client)

    expect(observedSignal?.aborted).toBe(false)

    unmount()

    expect(observedSignal?.aborted).toBe(true)
  })

  it('reuses the last successful index snapshot immediately for the same client on remount', async () => {
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

    expect(readState()).toEqual({
      status: 'success',
      sessions: firstPayload.data,
      meta: firstPayload.meta,
    })
    expect(fetchSessionIndex).toHaveBeenCalledTimes(2)
  })

  it('reuses the last empty index snapshot immediately but does not reuse errors', async () => {
    const emptyPayload = buildIndexResponse([])
    const errorPayload: SessionApiResult<SessionIndexResponse> = {
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
    }
    const pendingRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchEmptyIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: emptyPayload })
      .mockReturnValueOnce(pendingRequest.promise)
    const emptyClient = createClient(fetchEmptyIndex)

    const emptyRender = renderStateProbe(emptyClient)

    await waitFor(() => expect(readState()).toEqual({ status: 'empty' }))
    emptyRender.unmount()
    renderStateProbe(emptyClient)

    expect(readState()).toEqual({ status: 'empty' })

    cleanup()

    const fetchErrorIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce(errorPayload)
      .mockReturnValueOnce(pendingRequest.promise)
    const errorClient = createClient(fetchErrorIndex)
    const errorRender = renderStateProbe(errorClient)

    await waitFor(() => expect(readState()).toEqual(errorPayload))
    errorRender.unmount()
    renderStateProbe(errorClient)

    expect(readState()).toEqual({ status: 'loading' })
  })

  it('reloads the session index and preserves the previous snapshot while refreshing', async () => {
    const initialPayload = buildIndexResponse()
    const refreshedPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-c',
        updated_at: '2026-04-27T11:15:00Z',
      },
      {
        ...initialPayload.data[0],
        id: 'session-b',
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
  })

  it('returns an empty reload outcome without treating it as loading or error', async () => {
    const initialPayload = buildIndexResponse()
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
    await act(async () => {
      reloadRequest.resolve({
        status: 'success',
        data: buildIndexResponse([]),
      })

      await expect(reloadPromise).resolves.toEqual({ status: 'empty' })
    })
    await waitFor(() => expect(readRefreshing()).toBe(false))
    expect(readState()).toEqual({ status: 'empty' })
  })

  it('returns a reload error outcome without replacing the current snapshot', async () => {
    const initialPayload = buildIndexResponse()
    const reloadError: SessionApiResult<SessionIndexResponse> = {
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
    }
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

    await act(async () => {
      reloadRequest.resolve(reloadError)

      await expect(reloadPromise).resolves.toEqual(reloadError)
    })
    await waitFor(() => expect(readRefreshing()).toBe(false))
    expect(readState()).toEqual({
      status: 'success',
      sessions: initialPayload.data,
      meta: initialPayload.meta,
    })
  })

  it('ignores stale reload responses and keeps the superseded request on the prior settled state', async () => {
    const initialPayload = buildIndexResponse()
    const staleReloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const latestReloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const latestPayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-latest',
        updated_at: '2026-04-27T11:15:00Z',
      },
    ])
    const stalePayload = buildIndexResponse([
      {
        ...initialPayload.data[0],
        id: 'session-stale',
        updated_at: '2026-04-27T11:10:00Z',
      },
    ])
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(staleReloadRequest.promise)
      .mockReturnValueOnce(latestReloadRequest.promise)
    const client = createClient(fetchSessionIndex)

    const { ref } = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    let staleReloadPromise!: Promise<unknown>
    let latestReloadPromise!: Promise<unknown>
    await act(async () => {
      staleReloadPromise = reloadSessions(ref)
      latestReloadPromise = reloadSessions(ref)
    })

    await act(async () => {
      latestReloadRequest.resolve({ status: 'success', data: latestPayload })

      await expect(latestReloadPromise).resolves.toEqual({
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
      staleReloadRequest.resolve({ status: 'success', data: stalePayload })

      await expect(staleReloadPromise).resolves.toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      })
    })
    expect(readState()).toEqual({
      status: 'success',
      sessions: latestPayload.data,
      meta: latestPayload.meta,
    })
  })

  it('keeps the prior settled state when the hook unmounts before a reload completes', async () => {
    const initialPayload = buildIndexResponse()
    const reloadRequest = deferred<SessionApiResult<SessionIndexResponse>>()
    const fetchSessionIndex = vi
      .fn<SessionApiClient['fetchSessionIndex']>()
      .mockResolvedValueOnce({ status: 'success', data: initialPayload })
      .mockReturnValueOnce(reloadRequest.promise)
    const client = createClient(fetchSessionIndex)

    const view = renderStateProbe(client)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      }),
    )

    let reloadPromise!: Promise<unknown>
    await act(async () => {
      reloadPromise = reloadSessions(view.ref)
    })

    view.unmount()
    await act(async () => {
      reloadRequest.resolve({ status: 'success', data: buildIndexResponse([]) })

      await expect(reloadPromise).resolves.toEqual({
        status: 'success',
        sessions: initialPayload.data,
        meta: initialPayload.meta,
      })
    })
  })
})

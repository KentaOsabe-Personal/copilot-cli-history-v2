import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type {
  SessionApiClient,
  SessionApiResult,
  SessionDetailResponse,
  SessionIndexResponse,
} from '../../../../src/features/sessions/api/sessionApi.types.ts'
import { useSessionDetail } from '../../../../src/features/sessions/hooks/useSessionDetail.ts'

function deferred<T>() {
  let resolve!: (value: T) => void

  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })

  return { promise, resolve }
}

function createClient(
  fetchSessionDetail: SessionApiClient['fetchSessionDetail'],
  fetchSessionDetailWithRaw: SessionApiClient['fetchSessionDetailWithRaw'] = vi.fn<
    SessionApiClient['fetchSessionDetailWithRaw']
  >(async (): Promise<SessionApiResult<SessionDetailResponse>> => {
    throw new Error('fetchSessionDetailWithRaw should not be called in useSessionDetail tests')
  }),
): SessionApiClient {
  return {
    fetchSessionIndex: vi.fn<
      SessionApiClient['fetchSessionIndex']
    >(async (): Promise<SessionApiResult<SessionIndexResponse>> => {
      throw new Error('fetchSessionIndex should not be called in useSessionDetail tests')
    }),
    fetchSessionDetail,
    fetchSessionDetailWithRaw,
    syncHistory: vi.fn<SessionApiClient['syncHistory']>(async () => {
      throw new Error('syncHistory should not be called in useSessionDetail tests')
    }),
  }
}

function buildDetail(sessionId: string): SessionDetailResponse {
  return {
    data: {
      id: sessionId,
      source_format: 'current',
      created_at: '2026-04-26T09:00:00Z',
      updated_at: '2026-04-26T09:05:00Z',
      work_context: {
        cwd: `/workspace/${sessionId}`,
        git_root: `/workspace/${sessionId}`,
        repository: 'octo/example',
        branch: 'main',
      },
      selected_model: 'gpt-5.4',
      source_state: 'complete',
      degraded: false,
      raw_included: false,
      issues: [],
      message_snapshots: [],
      conversation: {
        entries: [],
        message_count: 0,
        empty_reason: 'no_events',
        summary: {
          has_conversation: false,
          message_count: 0,
          preview: null,
          activity_count: 0,
        },
      },
      activity: {
        entries: [],
      },
      timeline: [],
    },
  }
}

function StateProbe({
  client,
  sessionId,
}: {
  client: SessionApiClient
  sessionId: string
}) {
  const { state, requestRaw } = useSessionDetail(sessionId, { client })

  return (
    <>
      <pre data-testid="state">{JSON.stringify(state)}</pre>
      <button type="button" onClick={requestRaw}>
        raw
      </button>
    </>
  )
}

function readState() {
  return JSON.parse(screen.getByTestId('state').textContent ?? 'null')
}

describe('useSessionDetail', () => {
  /**
   * 概要・目的: 「starts in loading and transitions to success for the active session id」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「starts in loading and transitions to success for the active session id」の条件・入力・操作を実行する。
   * 期待値: 「starts in loading and transitions to success for the active session id」で示す状態または振る舞いが成立すること。
   */
  it('starts in loading and transitions to success for the active session id', async () => {
    const request = deferred<SessionApiResult<SessionDetailResponse>>()
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>(() => request.promise)
    const client = createClient(fetchSessionDetail)

    render(<StateProbe client={client} sessionId="session-123" />)

    expect(readState()).toEqual({
      status: 'loading',
      sessionId: 'session-123',
    })

    request.resolve({
      status: 'success',
      data: buildDetail('session-123'),
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessionId: 'session-123',
        detail: buildDetail('session-123').data,
        rawStatus: 'idle',
      }),
    )
  })

  /**
   * 概要・目的: 「maps session_not_found to a dedicated not_found state」を通じて、HTTP レスポンスとエラー契約を検証する。
   * テストケース: 「maps session_not_found to a dedicated not_found state」の条件・入力・操作を実行する。
   * 期待値: session_not_found が a dedicated not_found state に変換されること。
   */
  it('maps session_not_found to a dedicated not_found state', async () => {
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>(async () => ({
      status: 'error',
      error: {
        kind: 'not_found',
        httpStatus: 404,
        code: 'session_not_found',
        message: 'session was not found',
        details: {
          session_id: 'missing-session',
        },
      },
    }))
    const client = createClient(fetchSessionDetail)

    render(<StateProbe client={client} sessionId="missing-session" />)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'not_found',
        sessionId: 'missing-session',
      }),
    )
  })

  /**
   * 概要・目的: 「maps backend, network, and config failures to an error state」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「maps backend, network, and config failures to an error state」の条件・入力・操作を実行する。
   * 期待値: backend, network, and config failures が an error state に変換されること。
   */
  it('maps backend, network, and config failures to an error state', async () => {
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>(async () => ({
      status: 'error',
      error: {
        kind: 'network',
        code: 'network_error',
        message: 'Network request failed',
        details: {
          cause: 'Failed to fetch',
        },
      },
    }))
    const client = createClient(fetchSessionDetail)

    render(<StateProbe client={client} sessionId="session-500" />)

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'error',
        sessionId: 'session-500',
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
  })

  /**
   * 概要・目的: 「aborts the previous request and ignores its late response when the route param changes」を通じて、HTTP
   *   レスポンスとエラー契約を検証する。
   * テストケース: 「aborts the previous request and ignores its late response when the route param
   *   changes」の条件・入力・操作を実行する。
   * 期待値: 「aborts the previous request and ignores its late response when the route param
   *   changes」で示す状態または振る舞いが成立すること。
   */
  it('aborts the previous request and ignores its late response when the route param changes', async () => {
    const sessionARequest = deferred<SessionApiResult<SessionDetailResponse>>()
    const sessionBRequest = deferred<SessionApiResult<SessionDetailResponse>>()
    const observedSignals: AbortSignal[] = []
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>((sessionId, signal) => {
      if (signal != null) {
        observedSignals.push(signal)
      }

      if (sessionId === 'session-a') {
        return sessionARequest.promise
      }

      return sessionBRequest.promise
    })
    const client = createClient(fetchSessionDetail)

    const { rerender } = render(<StateProbe client={client} sessionId="session-a" />)

    expect(readState()).toEqual({
      status: 'loading',
      sessionId: 'session-a',
    })

    rerender(<StateProbe client={client} sessionId="session-b" />)

    expect(observedSignals[0]?.aborted).toBe(true)
    expect(readState()).toEqual({
      status: 'loading',
      sessionId: 'session-b',
    })

    sessionARequest.resolve({
      status: 'success',
      data: buildDetail('session-a'),
    })

    await Promise.resolve()

    expect(readState()).toEqual({
      status: 'loading',
      sessionId: 'session-b',
    })

    sessionBRequest.resolve({
      status: 'success',
      data: buildDetail('session-b'),
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessionId: 'session-b',
        detail: buildDetail('session-b').data,
        rawStatus: 'idle',
      }),
    )
  })

  /**
   * 概要・目的: 「returns to loading when the client changes for the same session id」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「returns to loading when the client changes for the same session id」の条件・入力・操作を実行する。
   * 期待値: to loading when the client changes for the same session id を返すこと。
   */
  it('returns to loading when the client changes for the same session id', async () => {
    const clientARequest = deferred<SessionApiResult<SessionDetailResponse>>()
    const clientBRequest = deferred<SessionApiResult<SessionDetailResponse>>()
    const clientA = createClient(vi.fn<SessionApiClient['fetchSessionDetail']>(() => clientARequest.promise))
    const clientB = createClient(vi.fn<SessionApiClient['fetchSessionDetail']>(() => clientBRequest.promise))

    const { rerender } = render(<StateProbe client={clientA} sessionId="session-123" />)

    clientARequest.resolve({
      status: 'success',
      data: buildDetail('session-123'),
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'success',
        sessionId: 'session-123',
        detail: buildDetail('session-123').data,
        rawStatus: 'idle',
      }),
    )

    rerender(<StateProbe client={clientB} sessionId="session-123" />)

    expect(readState()).toEqual({
      status: 'loading',
      sessionId: 'session-123',
    })

    clientBRequest.resolve({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 503,
        code: 'service_unavailable',
        message: 'service unavailable',
        details: {},
      },
    })

    await waitFor(() =>
      expect(readState()).toEqual({
        status: 'error',
        sessionId: 'session-123',
        error: {
          kind: 'backend',
          httpStatus: 503,
          code: 'service_unavailable',
          message: 'service unavailable',
          details: {},
        },
      }),
    )
  })

  /**
   * 概要・目的: 「keeps the normal detail visible while explicitly loading raw detail」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「keeps the normal detail visible while explicitly loading raw detail」の条件・入力・操作を実行する。
   * 期待値: the normal detail visible while explicitly loading raw detail が維持されること。
   */
  it('keeps the normal detail visible while explicitly loading raw detail', async () => {
    const rawRequest = deferred<SessionApiResult<SessionDetailResponse>>()
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>(async () => ({
      status: 'success',
      data: buildDetail('session-123'),
    }))
    const fetchSessionDetailWithRaw = vi.fn<SessionApiClient['fetchSessionDetailWithRaw']>(
      () => rawRequest.promise,
    )
    const client = createClient(fetchSessionDetail, fetchSessionDetailWithRaw)
    const user = userEvent.setup()

    render(<StateProbe client={client} sessionId="session-123" />)

    await waitFor(() =>
      expect(readState()).toMatchObject({
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'idle',
        detail: buildDetail('session-123').data,
      }),
    )

    await user.click(screen.getByRole('button', { name: 'raw' }))

    expect(fetchSessionDetailWithRaw).toHaveBeenCalledWith('session-123', expect.any(AbortSignal))
    expect(readState()).toMatchObject({
      status: 'success',
      sessionId: 'session-123',
      rawStatus: 'loading',
      detail: buildDetail('session-123').data,
    })

    rawRequest.resolve({
      status: 'success',
      data: {
        data: {
          ...buildDetail('session-123').data,
          raw_included: true,
        },
      },
    })

    await waitFor(() =>
      expect(readState()).toMatchObject({
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'included',
        detail: {
          raw_included: true,
        },
      }),
    )
  })

  /**
   * 概要・目的: 「keeps conversation detail visible when raw explicit request fails」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「keeps conversation detail visible when raw explicit request fails」の条件・入力・操作を実行する。
   * 期待値: conversation detail visible when raw explicit request fails が維持されること。
   */
  it('keeps conversation detail visible when raw explicit request fails', async () => {
    const fetchSessionDetail = vi.fn<SessionApiClient['fetchSessionDetail']>(async () => ({
      status: 'success',
      data: buildDetail('session-123'),
    }))
    const fetchSessionDetailWithRaw = vi.fn<SessionApiClient['fetchSessionDetailWithRaw']>(async () => ({
      status: 'error',
      error: {
        kind: 'network',
        code: 'network_error',
        message: 'Network request failed',
        details: {
          cause: 'offline',
        },
      },
    }))
    const client = createClient(fetchSessionDetail, fetchSessionDetailWithRaw)
    const user = userEvent.setup()

    render(<StateProbe client={client} sessionId="session-123" />)

    await waitFor(() => expect(readState().status).toBe('success'))

    await user.click(screen.getByRole('button', { name: 'raw' }))

    await waitFor(() =>
      expect(readState()).toMatchObject({
        status: 'success',
        sessionId: 'session-123',
        rawStatus: 'error',
        detail: buildDetail('session-123').data,
        rawError: {
          kind: 'network',
          code: 'network_error',
        },
      }),
    )
  })
})

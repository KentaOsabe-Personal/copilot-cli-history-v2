import { describe, expect, it, vi } from 'vitest'

import { createSessionApiClient } from './sessionApi'

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
    ...init,
  })
}

function buildHistorySyncResponse() {
  return {
    data: {
      sync_run: {
        id: 42,
        status: 'completed_with_issues',
        started_at: '2026-04-30T09:00:00Z',
        finished_at: '2026-04-30T09:00:05Z',
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

describe('createSessionApiClient', () => {
  it('returns success for the session index response without changing backend order', async () => {
    const payload = {
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
          issues: [
            {
              code: 'legacy.partial',
              severity: 'warning',
              message: 'legacy payload was incomplete',
              source_path: '/tmp/history-session-state/legacy.json',
              scope: 'session',
              event_sequence: null,
            },
          ],
        },
      ],
      meta: {
        count: 2,
        partial_results: true,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.fetchSessionIndex()).resolves.toEqual({
      status: 'success',
      data: payload,
    })
    expect(String(fetchMock.mock.calls[0][0])).toBe('http://localhost:30000/api/sessions')
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })
  })

  it('serializes the explicit default 7-day date query for the session index in a stable order', async () => {
    const payload = {
      data: [],
      meta: {
        count: 0,
        partial_results: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(
      client.fetchSessionIndex({
        query: {
          from: '2026-04-28T00:00:00+09:00',
          to: '2026-05-04T23:59:59.999999+09:00',
        },
      }),
    ).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions?from=2026-04-28T00%3A00%3A00%2B09%3A00&to=2026-05-04T23%3A59%3A59.999999%2B09%3A00',
    )
  })

  it('omits empty date query values while keeping defined values', async () => {
    const payload = {
      data: [],
      meta: {
        count: 0,
        partial_results: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(
      client.fetchSessionIndex({
        query: {
          from: '2026-05-01T00:00:00+09:00',
          to: '',
        },
      }),
    ).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions?from=2026-05-01T00%3A00%3A00%2B09%3A00',
    )
  })

  it('serializes a normalized search query after date range parameters', async () => {
    const payload = {
      data: [],
      meta: {
        count: 0,
        partial_results: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(
      client.fetchSessionIndex({
        query: {
          from: '2026-04-28T00:00:00+09:00',
          to: '2026-05-04T23:59:59.999999+09:00',
          search: 'apply patch',
        },
      }),
    ).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions?from=2026-04-28T00%3A00%3A00%2B09%3A00&to=2026-05-04T23%3A59%3A59.999999%2B09%3A00&search=apply+patch',
    )
  })

  it('omits blank search query values', async () => {
    const payload = {
      data: [],
      meta: {
        count: 0,
        partial_results: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(
      client.fetchSessionIndex({
        query: {
          search: '',
        },
      }),
    ).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe('http://localhost:30000/api/sessions')
  })

  it('serializes a to-only date query without adding an empty from value', async () => {
    const payload = {
      data: [],
      meta: {
        count: 0,
        partial_results: false,
      },
    }
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(
      client.fetchSessionIndex({
        query: {
          from: '',
          to: '2026-05-07T23:59:59.999999+09:00',
        },
      }),
    ).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions?to=2026-05-07T23%3A59%3A59.999999%2B09%3A00',
    )
  })

  it('fetches normal and raw-explicit detail through separate typed client methods', async () => {
    const payload = {
      data: {
        id: 'session-raw',
        source_format: 'current',
        created_at: '2026-04-26T10:00:00Z',
        updated_at: '2026-04-26T10:05:00Z',
        work_context: {
          cwd: '/workspace/session-raw',
          git_root: '/workspace/session-raw',
          repository: 'octo/example',
          branch: 'feature/raw',
        },
        selected_model: null,
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
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(payload))
      .mockResolvedValueOnce(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.fetchSessionDetail('session-raw')).resolves.toEqual({
      status: 'success',
      data: payload,
    })
    await expect(client.fetchSessionDetailWithRaw('session-raw')).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions/session-raw',
    )
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      'http://localhost:30000/api/sessions/session-raw?include_raw=true',
    )
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })
  })

  it('posts sync history without a body and returns the sync payload unchanged', async () => {
    const payload = buildHistorySyncResponse()
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.syncHistory()).resolves.toEqual({
      status: 'success',
      data: payload,
    })

    expect(String(fetchMock.mock.calls[0][0])).toBe('http://localhost:30000/api/history/sync')
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'POST',
      headers: {
        Accept: 'application/json',
      },
    })
    expect(fetchMock.mock.calls[0][1]?.body).toBeUndefined()
  })

  it('preserves sync conflicts as backend errors with http status and code', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'history_sync_running',
            message: 'history sync is already running',
            details: {
              sync_run_id: 7,
              started_at: '2026-04-30T08:55:00Z',
            },
          },
        },
        { status: 409 },
      ),
    )
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.syncHistory()).resolves.toEqual({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 409,
        code: 'history_sync_running',
        message: 'history sync is already running',
        details: {
          sync_run_id: 7,
          started_at: '2026-04-30T08:55:00Z',
        },
      },
    })
  })

  it('preserves root and persistence sync failures as backend errors', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'root_missing',
              message: 'history root does not exist',
              details: {
                path: '/tmp/.copilot',
              },
            },
            meta: buildHistorySyncResponse().data,
          },
          { status: 503 },
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'history_sync_failed',
              message: 'history sync failed',
              details: {
                failure_class: 'ActiveRecord::RecordInvalid',
                sync_run_id: 8,
              },
            },
            meta: buildHistorySyncResponse().data,
          },
          { status: 500 },
        ),
      )
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.syncHistory()).resolves.toEqual({
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
    })

    await expect(client.syncHistory()).resolves.toEqual({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 500,
        code: 'history_sync_failed',
        message: 'history sync failed',
        details: {
          failure_class: 'ActiveRecord::RecordInvalid',
          sync_run_id: 8,
        },
      },
    })
  })

  it('returns a config error before requesting when sync history is called without an API base URL', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: {},
    })

    await expect(client.syncHistory()).resolves.toEqual({
      status: 'error',
      error: {
        kind: 'config',
        code: 'api_base_url_missing',
        message: 'VITE_API_BASE_URL is not configured',
        details: {
          env: 'VITE_API_BASE_URL',
        },
      },
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('normalizes sync network failures into a network error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.syncHistory()).resolves.toEqual({
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
  })

  it('normalizes a detail 404 session_not_found into a not_found error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'session_not_found',
            message: 'session was not found',
            details: {
              session_id: 'missing-session',
            },
          },
        },
        { status: 404 },
      ),
    )
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.fetchSessionDetail('missing-session')).resolves.toEqual({
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
    })
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      'http://localhost:30000/api/sessions/missing-session',
    )
  })

  it('normalizes backend failures into a backend error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'root_missing',
            message: 'history root does not exist',
            details: {
              path: '/tmp/.copilot',
            },
          },
        },
        { status: 503 },
      ),
    )
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.fetchSessionIndex()).resolves.toEqual({
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
    })
  })

  it('returns a config error before requesting when the API base URL is missing', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: {},
    })

    await expect(client.fetchSessionIndex()).resolves.toEqual({
      status: 'error',
      error: {
        kind: 'config',
        code: 'api_base_url_missing',
        message: 'VITE_API_BASE_URL is not configured',
        details: {
          env: 'VITE_API_BASE_URL',
        },
      },
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns a config error before requesting when the API base URL is malformed', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: '/relative-only' },
    })

    await expect(client.fetchSessionIndex()).resolves.toEqual({
      status: 'error',
      error: {
        kind: 'config',
        code: 'api_base_url_invalid',
        message: 'VITE_API_BASE_URL must be an absolute URL',
        details: {
          env: 'VITE_API_BASE_URL',
          value: '/relative-only',
        },
      },
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('normalizes network failures into a network error', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = createSessionApiClient({
      fetchImpl: fetchMock,
      env: { VITE_API_BASE_URL: 'http://localhost:30000' },
    })

    await expect(client.fetchSessionIndex()).resolves.toEqual({
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
  })
})

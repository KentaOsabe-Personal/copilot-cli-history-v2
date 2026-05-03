import { useCallback, useEffect, useRef, useState } from 'react'

import { sessionApiClient } from '../api/sessionApi.ts'
import type {
  SessionApiClient,
  SessionApiError,
  SessionApiResult,
  SessionIndexMeta,
  SessionIndexResponse,
  SessionSummary,
} from '../api/sessionApi.types.ts'

export type SessionIndexState =
  | { status: 'loading' }
  | { status: 'empty' }
  | {
      status: 'success'
      sessions: readonly SessionSummary[]
      meta: SessionIndexMeta
    }
  | {
      status: 'error'
      error: SessionApiError
    }

export interface UseSessionIndexOptions {
  client?: SessionApiClient
}

export interface UseSessionIndexResult {
  state: SessionIndexState
  isRefreshing: boolean
  reloadSessions(): Promise<SessionIndexSettledState>
}

export type SessionIndexSettledState = Exclude<SessionIndexState, { status: 'loading' }>

type SettledSessionIndexState = SessionIndexSettledState
type ReusableSessionIndexState = Extract<SessionIndexState, { status: 'success' | 'empty' }>
type SettledStateEnvelope = {
  client: SessionApiClient
  state: SettledSessionIndexState
}
type ActiveRequest = {
  id: number
  controller: AbortController
}

let lastReusableSnapshot: {
  client: SessionApiClient
  state: ReusableSessionIndexState
} | null = null

export function useSessionIndex(
  options: UseSessionIndexOptions = {},
): UseSessionIndexResult {
  const client = options.client ?? sessionApiClient
  const [settledState, setSettledState] = useState<SettledStateEnvelope | null>(() => lastReusableSnapshot)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const settledStateRef = useRef<SettledStateEnvelope | null>(lastReusableSnapshot)
  const activeRequestRef = useRef<ActiveRequest | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    settledStateRef.current = settledState
  }, [settledState])

  const applySettledState = useCallback(
    (nextState: SettledSessionIndexState) => {
      if (isReusableSessionIndexState(nextState)) {
        lastReusableSnapshot = {
          client,
          state: nextState,
        }
      }

      const nextEnvelope = {
        client,
        state: nextState,
      }

      settledStateRef.current = nextEnvelope
      setSettledState(nextEnvelope)
    },
    [client],
  )

  const reloadSessions = useCallback(async (): Promise<SessionIndexSettledState> => {
    requestIdRef.current += 1
    const requestId = requestIdRef.current
    const controller = new AbortController()
    const previousRequest = activeRequestRef.current
    const previousState = currentSettledStateForClient(settledStateRef.current, client)

    activeRequestRef.current = { id: requestId, controller }
    previousRequest?.controller.abort()
    setIsRefreshing(true)

    const result = await client.fetchSessionIndex({ signal: controller.signal })

    if (controller.signal.aborted || activeRequestRef.current?.id !== requestId) {
      if (activeRequestRef.current?.id === requestId) {
        activeRequestRef.current = null
        setIsRefreshing(false)
      }

      return previousState ?? toSettledState(result)
    }

    activeRequestRef.current = null
    setIsRefreshing(false)

    const nextState = toSettledState(result)

    if (
      nextState.status === 'error' &&
      previousState != null &&
      isReusableSessionIndexState(previousState)
    ) {
      return nextState
    }

    applySettledState(nextState)

    return nextState
  }, [applySettledState, client])

  useEffect(() => {
    requestIdRef.current += 1
    const requestId = requestIdRef.current
    const controller = new AbortController()
    const previousRequest = activeRequestRef.current

    activeRequestRef.current = { id: requestId, controller }
    previousRequest?.controller.abort()

    void client.fetchSessionIndex({ signal: controller.signal }).then((result) => {
      if (controller.signal.aborted || activeRequestRef.current?.id !== requestId) {
        if (activeRequestRef.current?.id === requestId) {
          activeRequestRef.current = null
          setIsRefreshing(false)
        }

        return
      }

      activeRequestRef.current = null
      setIsRefreshing(false)
      applySettledState(toSettledState(result))
    })

    return () => {
      controller.abort()
      activeRequestRef.current?.controller.abort()
      activeRequestRef.current = null
    }
  }, [applySettledState, client])

  if (settledState == null || settledState.client !== client) {
    return {
      state: { status: 'loading' },
      isRefreshing: false,
      reloadSessions,
    }
  }

  return {
    state: settledState.state,
    isRefreshing,
    reloadSessions,
  }
}

function currentSettledStateForClient(
  settledState: SettledStateEnvelope | null,
  client: SessionApiClient,
): SettledSessionIndexState | null {
  if (settledState == null || settledState.client !== client) {
    return null
  }

  return settledState.state
}

function isReusableSessionIndexState(
  state: SettledSessionIndexState,
): state is ReusableSessionIndexState {
  return state.status === 'success' || state.status === 'empty'
}

function toSettledState(
  result: SessionApiResult<SessionIndexResponse>,
): SettledSessionIndexState {
  if (result.status === 'error') {
    return {
      status: 'error',
      error: result.error,
    }
  }

  if (result.data.data.length === 0) {
    return { status: 'empty' }
  }

  return {
    status: 'success',
    sessions: result.data.data,
    meta: result.data.meta,
  }
}

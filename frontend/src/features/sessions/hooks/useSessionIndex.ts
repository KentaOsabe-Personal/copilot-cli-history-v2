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
import {
  buildDefaultRange,
  buildQueryKey,
  resolveAppliedRange,
  toSessionIndexQuery,
  type SessionDateRangeDraft,
} from '../presentation/sessionDateFilter.ts'

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
  now?: () => Date
}

export interface UseSessionIndexResult {
  state: SessionIndexState
  appliedRange: SessionDateRangeDraft
  isRefreshing: boolean
  applyRange(range: SessionDateRangeDraft): Promise<SessionIndexSettledState>
  reloadSessions(): Promise<SessionIndexSettledState>
}

export type SessionIndexSettledState = Exclude<SessionIndexState, { status: 'loading' }>

type SettledSessionIndexState = SessionIndexSettledState
type ReusableSessionIndexState = Extract<SessionIndexState, { status: 'success' | 'empty' }>
type SettledStateEnvelope = {
  client: SessionApiClient
  queryKey: string
  state: SettledSessionIndexState
}
type ActiveRequest = {
  id: number
  controller: AbortController
}

const reusableSnapshots = new WeakMap<
  SessionApiClient,
  Map<string, ReusableSessionIndexState>
>()
const defaultNow = () => new Date()

export function useSessionIndex(
  options: UseSessionIndexOptions = {},
): UseSessionIndexResult {
  const client = options.client ?? sessionApiClient
  const now = options.now ?? defaultNow
  const [initialState] = useState(() => {
    const initialRange = buildDefaultRange(now())
    const queryKey = buildQueryKey(initialRange)
    const snapshot = readReusableSnapshot(client, queryKey)

    return {
      appliedRange: initialRange,
      settledState:
        snapshot == null
          ? null
          : ({
              client,
              queryKey,
              state: snapshot,
            } satisfies SettledStateEnvelope),
    }
  })
  const [appliedRange, setAppliedRange] = useState<SessionDateRangeDraft>(initialState.appliedRange)
  const [settledState, setSettledState] = useState<SettledStateEnvelope | null>(
    initialState.settledState,
  )
  const [isRefreshing, setIsRefreshing] = useState(false)
  const appliedRangeRef = useRef(appliedRange)
  const settledStateRef = useRef<SettledStateEnvelope | null>(settledState)
  const activeRequestRef = useRef<ActiveRequest | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    appliedRangeRef.current = appliedRange
  }, [appliedRange])

  useEffect(() => {
    settledStateRef.current = settledState
  }, [settledState])

  const applySettledState = useCallback(
    (queryKey: string, nextState: SettledSessionIndexState) => {
      if (isReusableSessionIndexState(nextState)) {
        writeReusableSnapshot(client, queryKey, nextState)
      }

      const nextEnvelope = {
        client,
        queryKey,
        state: nextState,
      }

      settledStateRef.current = nextEnvelope
      setSettledState(nextEnvelope)
    },
    [client],
  )

  const performRequest = useCallback(async ({
    range,
    queryKey,
    preserveVisibleState,
    preserveSnapshotOnError,
  }: {
    range: SessionDateRangeDraft
    queryKey: string
    preserveVisibleState: boolean
    preserveSnapshotOnError: boolean
  }): Promise<SessionIndexSettledState> => {
    requestIdRef.current += 1
    const requestId = requestIdRef.current
    const controller = new AbortController()
    const previousRequest = activeRequestRef.current
    const previousState = currentSettledStateForClient(settledStateRef.current, client)

    activeRequestRef.current = { id: requestId, controller }
    previousRequest?.controller.abort()
    setIsRefreshing(preserveVisibleState)

    if (!preserveVisibleState) {
      settledStateRef.current = null
      setSettledState(null)
    }

    const result = await client.fetchSessionIndex({
      signal: controller.signal,
      query: toSessionIndexQuery(range),
    })

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
      preserveSnapshotOnError &&
      previousState != null &&
      isReusableSessionIndexState(previousState)
    ) {
      return nextState
    }

    applySettledState(queryKey, nextState)

    return nextState
  }, [applySettledState, client])

  const applyRange = useCallback(async (range: SessionDateRangeDraft): Promise<SessionIndexSettledState> => {
    const nextRange = resolveAppliedRange(range, now())
    const queryKey = buildQueryKey(nextRange)

    appliedRangeRef.current = nextRange
    setAppliedRange(nextRange)

    return performRequest({
      range: nextRange,
      queryKey,
      preserveVisibleState: false,
      preserveSnapshotOnError: false,
    })
  }, [now, performRequest])

  const reloadSessions = useCallback(async (): Promise<SessionIndexSettledState> => {
    const nextRange = appliedRangeRef.current

    return performRequest({
      range: nextRange,
      queryKey: buildQueryKey(nextRange),
      preserveVisibleState: true,
      preserveSnapshotOnError: true,
    })
  }, [performRequest])

  useEffect(() => {
    let disposed = false
    const initialRange = appliedRangeRef.current
    const initialQueryKey = buildQueryKey(initialRange)
    const hasReusableSnapshot = readReusableSnapshot(client, initialQueryKey) != null

    void performRequest({
      range: initialRange,
      queryKey: initialQueryKey,
      preserveVisibleState: hasReusableSnapshot,
      preserveSnapshotOnError: hasReusableSnapshot,
    }).then((result) => {
      if (!disposed && hasReusableSnapshot && result.status === 'error') {
        applySettledState(initialQueryKey, result)
      }
    })

    return () => {
      disposed = true
      activeRequestRef.current?.controller.abort()
      activeRequestRef.current = null
    }
  }, [applySettledState, client, performRequest])

  if (settledState == null || settledState.client !== client) {
    return {
      state: { status: 'loading' },
      appliedRange,
      isRefreshing: false,
      applyRange,
      reloadSessions,
    }
  }

  return {
    state: settledState.state,
    appliedRange,
    isRefreshing,
    applyRange,
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

function readReusableSnapshot(
  client: SessionApiClient,
  queryKey: string,
): ReusableSessionIndexState | null {
  return reusableSnapshots.get(client)?.get(queryKey) ?? null
}

function writeReusableSnapshot(
  client: SessionApiClient,
  queryKey: string,
  state: ReusableSessionIndexState,
) {
  const clientSnapshots = reusableSnapshots.get(client)

  if (clientSnapshots != null) {
    clientSnapshots.set(queryKey, state)

    return
  }

  reusableSnapshots.set(client, new Map([[queryKey, state]]))
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

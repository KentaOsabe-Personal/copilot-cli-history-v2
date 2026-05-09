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
  resolveAppliedRange,
  type SessionDateRangeDraft,
} from '../presentation/sessionDateFilter.ts'
import {
  buildCriteriaKey,
  normalizeSearchTerm,
  toSessionIndexQuery,
  type SessionIndexCriteria,
} from '../presentation/sessionIndexCriteria.ts'

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
  appliedSearchTerm: string
  isRefreshing: boolean
  applyRange(range: SessionDateRangeDraft): Promise<SessionIndexSettledState>
  applySearch(searchTerm: string): Promise<SessionIndexSettledState>
  clearSearch(): Promise<SessionIndexSettledState>
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
    const initialCriteria = {
      range: initialRange,
      searchTerm: '',
    }
    const queryKey = buildCriteriaKey(initialCriteria)
    const snapshot = readReusableSnapshot(client, queryKey)

    return {
      appliedCriteria: initialCriteria,
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
  const [appliedCriteria, setAppliedCriteria] = useState<SessionIndexCriteria>(initialState.appliedCriteria)
  const [settledState, setSettledState] = useState<SettledStateEnvelope | null>(
    initialState.settledState,
  )
  const [isRefreshing, setIsRefreshing] = useState(false)
  const appliedCriteriaRef = useRef(appliedCriteria)
  const settledStateRef = useRef<SettledStateEnvelope | null>(settledState)
  const activeRequestRef = useRef<ActiveRequest | null>(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    appliedCriteriaRef.current = appliedCriteria
  }, [appliedCriteria])

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
    criteria,
    queryKey,
    preserveVisibleState,
    preserveSnapshotOnError,
  }: {
    criteria: SessionIndexCriteria
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
      query: toSessionIndexQuery(criteria),
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
    const nextCriteria = {
      range: nextRange,
      searchTerm: appliedCriteriaRef.current.searchTerm,
    }
    const queryKey = buildCriteriaKey(nextCriteria)

    appliedCriteriaRef.current = nextCriteria
    setAppliedCriteria(nextCriteria)

    return performRequest({
      criteria: nextCriteria,
      queryKey,
      preserveVisibleState: false,
      preserveSnapshotOnError: false,
    })
  }, [now, performRequest])

  const applySearch = useCallback(async (searchTerm: string): Promise<SessionIndexSettledState> => {
    const nextCriteria = {
      range: appliedCriteriaRef.current.range,
      searchTerm: normalizeSearchTerm(searchTerm),
    }
    const queryKey = buildCriteriaKey(nextCriteria)

    appliedCriteriaRef.current = nextCriteria
    setAppliedCriteria(nextCriteria)

    return performRequest({
      criteria: nextCriteria,
      queryKey,
      preserveVisibleState: false,
      preserveSnapshotOnError: false,
    })
  }, [performRequest])

  const clearSearch = useCallback(async (): Promise<SessionIndexSettledState> => {
    return applySearch('')
  }, [applySearch])

  const reloadSessions = useCallback(async (): Promise<SessionIndexSettledState> => {
    const nextCriteria = appliedCriteriaRef.current

    return performRequest({
      criteria: nextCriteria,
      queryKey: buildCriteriaKey(nextCriteria),
      preserveVisibleState: true,
      preserveSnapshotOnError: true,
    })
  }, [performRequest])

  useEffect(() => {
    let disposed = false
    const initialCriteria = appliedCriteriaRef.current
    const initialQueryKey = buildCriteriaKey(initialCriteria)
    const hasReusableSnapshot = readReusableSnapshot(client, initialQueryKey) != null

    void performRequest({
      criteria: initialCriteria,
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
      appliedRange: appliedCriteria.range,
      appliedSearchTerm: appliedCriteria.searchTerm,
      isRefreshing: false,
      applyRange,
      applySearch,
      clearSearch,
      reloadSessions,
    }
  }

  return {
    state: settledState.state,
    appliedRange: appliedCriteria.range,
    appliedSearchTerm: appliedCriteria.searchTerm,
    isRefreshing,
    applyRange,
    applySearch,
    clearSearch,
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

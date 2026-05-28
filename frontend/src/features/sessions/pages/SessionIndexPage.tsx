import { useEffect, useId, useMemo, useState } from 'react'

import HistorySyncControl from '../components/HistorySyncControl.tsx'
import HistorySyncStatus from '../components/HistorySyncStatus.tsx'
import SessionDateFilterForm from '../components/SessionDateFilterForm.tsx'
import SessionDirectoryTabs from '../components/SessionDirectoryTabs.tsx'
import SessionEmptyState from '../components/SessionEmptyState.tsx'
import SessionList from '../components/SessionList.tsx'
import SessionSearchForm from '../components/SessionSearchForm.tsx'
import StatusPanel from '../components/StatusPanel.tsx'
import { useHistorySync } from '../hooks/useHistorySync.ts'
import { useSessionIndex } from '../hooks/useSessionIndex.ts'
import {
  buildQueryKey,
  formatRangeLabel,
  type SessionDateRangeDraft,
} from '../presentation/sessionDateFilter.ts'
import {
  formatCriteriaLabel,
  type SessionIndexCriteria,
} from '../presentation/sessionIndexCriteria.ts'
import {
  buildSessionDirectoryTabs,
  coerceDirectoryTabKey,
  getSessionsForDirectoryTab,
  type SessionDirectoryTab,
  type SessionDirectoryTabKey,
} from '../presentation/sessionDirectoryTabs.ts'

interface DraftRangeState {
  appliedRangeKey: string
  draftRange: SessionDateRangeDraft
}

function SessionIndexPage() {
  const directoryTabsId = useId()
  const directoryPanelId = `${directoryTabsId}-panel`
  const {
    state,
    appliedRange,
    appliedSearchTerm,
    applyRange,
    applySearch,
    clearSearch,
    isRefreshing,
    reloadSessions,
  } = useSessionIndex()
  const { state: syncState, isSyncing, startSync } = useHistorySync({ reloadSessions })
  const appliedRangeKey = buildQueryKey(appliedRange)
  const [draftState, setDraftState] = useState<DraftRangeState>(() => ({
    appliedRangeKey,
    draftRange: appliedRange,
  }))
  const [selectedDirectoryTabKey, setSelectedDirectoryTabKey] =
    useState<SessionDirectoryTabKey>('all')
  const appliedRangeLabel = formatRangeLabel(appliedRange)
  const appliedCriteria: SessionIndexCriteria = {
    range: appliedRange,
    searchTerm: appliedSearchTerm,
  }
  const appliedCriteriaLabel = formatCriteriaLabel(appliedCriteria)
  const hasAppliedSearch = appliedSearchTerm !== ''
  const searchConditionErrorMessage = isSearchConditionError(state)
    ? '検索条件を確認してください。'
    : null
  const draftRange =
    draftState.appliedRangeKey === appliedRangeKey
      ? draftState.draftRange
      : appliedRange
  const directoryTabs = useMemo(
    () => (state.status === 'success' ? buildSessionDirectoryTabs(state.sessions).tabs : []),
    [state],
  )
  const coercedDirectoryTabKey =
    state.status === 'success'
      ? coerceDirectoryTabKey(selectedDirectoryTabKey, directoryTabs)
      : 'all'
  const visibleSessions =
    state.status === 'success'
      ? getSessionsForDirectoryTab(state.sessions, coercedDirectoryTabKey)
      : []
  const selectedDirectoryTab =
    state.status === 'success'
      ? directoryTabs.find((tab) => tab.key === coercedDirectoryTabKey) ?? null
      : null

  useEffect(() => {
    if (
      state.status !== 'success' ||
      selectedDirectoryTabKey === coercedDirectoryTabKey
    ) {
      return undefined
    }

    let shouldApply = true
    queueMicrotask(() => {
      if (shouldApply) {
        setSelectedDirectoryTabKey(coercedDirectoryTabKey)
      }
    })

    return () => {
      shouldApply = false
    }
  }, [coercedDirectoryTabKey, selectedDirectoryTabKey, state.status])

  const getDirectoryTabId = (key: SessionDirectoryTabKey) =>
    `${directoryTabsId}-tab-${encodeURIComponent(key)}`

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold text-white">セッション一覧</h2>
        <SessionDateFilterForm
          draftRange={draftRange}
          appliedRange={appliedRange}
          isApplying={state.status === 'loading' && !isRefreshing}
          onDraftChange={(nextDraftRange) => {
            setDraftState({
              appliedRangeKey,
              draftRange: nextDraftRange,
            })
          }}
          onApply={async (nextRange) => {
            await applyRange(nextRange)
          }}
        />
        <SessionSearchForm
          appliedSearchTerm={appliedSearchTerm}
          appliedCriteriaLabel={appliedCriteriaLabel}
          isApplying={state.status === 'loading' && !isRefreshing}
          backendErrorMessage={searchConditionErrorMessage}
          onApplySearch={async (nextSearchTerm) => {
            await applySearch(nextSearchTerm)
          }}
          onClearSearch={async () => {
            await clearSearch()
          }}
        />
        <HistorySyncControl isSyncing={isSyncing} onSync={startSync} />
      </div>

      <HistorySyncStatus state={syncState} />

      {state.status === 'loading' ? (
        <StatusPanel
          variant="loading"
          title={
            hasAppliedSearch
              ? '検索条件を含むセッション一覧を読み込んでいます'
              : 'セッション一覧を読み込んでいます'
          }
          message={
            hasAppliedSearch
              ? `現在の表示条件: ${appliedCriteriaLabel} のセッションを確認しています。`
              : `現在の表示範囲: ${appliedRangeLabel} のセッションを確認しています。`
          }
        />
      ) : null}

      {state.status === 'empty' ? (
        <SessionEmptyState
          appliedRangeLabel={appliedRangeLabel}
          appliedSearchTerm={appliedSearchTerm}
          syncState={syncState}
          isSyncing={isSyncing}
          onSync={startSync}
          onClearSearch={async () => {
            await clearSearch()
          }}
        />
      ) : null}

      {state.status === 'error' && isSearchConditionError(state) ? (
        <StatusPanel
          variant="error"
          title="検索条件を確認してください"
          message={`現在の表示条件: ${appliedCriteriaLabel} を見直して再度検索してください。`}
        />
      ) : null}

      {state.status === 'error' && !isSearchConditionError(state) ? (
        <StatusPanel
          variant="error"
          title="セッション一覧を表示できません"
          message={
            hasAppliedSearch
              ? `現在の表示条件: ${appliedCriteriaLabel} の一覧取得に失敗しました。時間をおいて再度開くか、条件を見直してください。`
              : `現在の表示範囲: ${appliedRangeLabel} の一覧取得に失敗しました。時間をおいて再度開いてください。`
          }
        />
      ) : null}

      {state.status === 'success' ? (
        <div className="flex flex-col gap-4">
          {hasAppliedSearch ? (
            <p className="text-sm text-slate-300">
              現在の表示条件: {appliedCriteriaLabel} の検索結果を表示しています。作業ディレクトリは一覧タブで切り替えられます。
            </p>
          ) : null}
          <SessionDirectoryTabs
            tabs={directoryTabs}
            selectedKey={coercedDirectoryTabKey}
            panelId={directoryPanelId}
            getTabId={getDirectoryTabId}
            onSelect={setSelectedDirectoryTabKey}
          />
          <div
            id={directoryPanelId}
            role="tabpanel"
            aria-labelledby={getDirectoryTabId(coercedDirectoryTabKey)}
            className="flex flex-col gap-3"
          >
            <SelectedDirectoryTabSummary tab={selectedDirectoryTab} />
            <SessionList sessions={visibleSessions} />
          </div>
        </div>
      ) : null}
    </section>
  )
}

interface SelectedDirectoryTabSummaryProps {
  tab: SessionDirectoryTab | null
}

function SelectedDirectoryTabSummary({ tab }: SelectedDirectoryTabSummaryProps) {
  if (tab == null || tab.kind === 'all') {
    return (
      <p className="text-sm text-slate-300">
        すべてのセッションを表示しています。
      </p>
    )
  }

  if (tab.kind === 'unset') {
    return (
      <p className="text-sm text-slate-300">
        作業ディレクトリが未設定のセッションを表示しています。
      </p>
    )
  }

  return (
    <p className="break-words text-sm text-slate-300">
      作業ディレクトリ: {tab.fullPath}
    </p>
  )
}

function isSearchConditionError(
  state: ReturnType<typeof useSessionIndex>['state'],
): state is Extract<ReturnType<typeof useSessionIndex>['state'], { status: 'error' }> {
  return (
    state.status === 'error' &&
    state.error.kind === 'backend' &&
    state.error.code === 'invalid_session_list_query' &&
    state.error.details.field === 'search'
  )
}

export default SessionIndexPage

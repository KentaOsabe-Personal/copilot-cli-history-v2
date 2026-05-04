import { useState } from 'react'

import HistorySyncControl from '../components/HistorySyncControl.tsx'
import HistorySyncStatus from '../components/HistorySyncStatus.tsx'
import SessionDateFilterForm from '../components/SessionDateFilterForm.tsx'
import SessionList from '../components/SessionList.tsx'
import SessionEmptyState from '../components/SessionEmptyState.tsx'
import StatusPanel from '../components/StatusPanel.tsx'
import { useHistorySync } from '../hooks/useHistorySync.ts'
import { useSessionIndex } from '../hooks/useSessionIndex.ts'
import {
  buildQueryKey,
  formatRangeLabel,
  type SessionDateRangeDraft,
} from '../presentation/sessionDateFilter.ts'

interface DraftRangeState {
  appliedRangeKey: string
  draftRange: SessionDateRangeDraft
}

function SessionIndexPage() {
  const { state, appliedRange, applyRange, isRefreshing, reloadSessions } = useSessionIndex()
  const { state: syncState, isSyncing, startSync } = useHistorySync({ reloadSessions })
  const appliedRangeKey = buildQueryKey(appliedRange)
  const [draftState, setDraftState] = useState<DraftRangeState>(() => ({
    appliedRangeKey,
    draftRange: appliedRange,
  }))
  const appliedRangeLabel = formatRangeLabel(appliedRange)
  const draftRange =
    draftState.appliedRangeKey === appliedRangeKey
      ? draftState.draftRange
      : appliedRange

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
        <HistorySyncControl isSyncing={isSyncing} onSync={startSync} />
      </div>

      <HistorySyncStatus state={syncState} />

      {state.status === 'loading' ? (
        <StatusPanel
          variant="loading"
          title="セッション一覧を読み込んでいます"
          message={`現在の表示範囲: ${appliedRangeLabel} のセッションを確認しています。`}
        />
      ) : null}

      {state.status === 'empty' ? (
        <SessionEmptyState
          appliedRangeLabel={appliedRangeLabel}
          syncState={syncState}
          isSyncing={isSyncing}
          onSync={startSync}
        />
      ) : null}

      {state.status === 'error' ? (
        <StatusPanel
          variant="error"
          title="セッション一覧を表示できません"
          message={`現在の表示範囲: ${appliedRangeLabel} の一覧取得に失敗しました。時間をおいて再度開いてください。`}
        />
      ) : null}

      {state.status === 'success' ? <SessionList sessions={state.sessions} /> : null}
    </section>
  )
}

export default SessionIndexPage

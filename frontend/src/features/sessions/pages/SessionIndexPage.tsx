import HistorySyncControl from '../components/HistorySyncControl.tsx'
import HistorySyncStatus from '../components/HistorySyncStatus.tsx'
import SessionList from '../components/SessionList.tsx'
import SessionEmptyState from '../components/SessionEmptyState.tsx'
import StatusPanel from '../components/StatusPanel.tsx'
import { useHistorySync } from '../hooks/useHistorySync.ts'
import { useSessionIndex } from '../hooks/useSessionIndex.ts'
import { formatRangeLabel } from '../presentation/sessionDateFilter.ts'

function SessionIndexPage() {
  const { state, appliedRange, reloadSessions } = useSessionIndex()
  const { state: syncState, isSyncing, startSync } = useHistorySync({ reloadSessions })

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold text-white">セッション一覧</h2>
        <HistorySyncControl isSyncing={isSyncing} onSync={startSync} />
      </div>

      <HistorySyncStatus state={syncState} />

      {state.status === 'loading' ? (
        <StatusPanel
          variant="loading"
          title="セッション一覧を読み込んでいます"
          message="保存済みセッションを確認しています。"
        />
      ) : null}

      {state.status === 'empty' ? (
        <SessionEmptyState
          appliedRangeLabel={formatRangeLabel(appliedRange)}
          syncState={syncState}
          isSyncing={isSyncing}
          onSync={startSync}
        />
      ) : null}

      {state.status === 'error' ? (
        <StatusPanel
          variant="error"
          title="セッション一覧を表示できません"
          message="一覧の取得に失敗しました。時間をおいて再度開いてください。"
        />
      ) : null}

      {state.status === 'success' ? <SessionList sessions={state.sessions} /> : null}
    </section>
  )
}

export default SessionIndexPage

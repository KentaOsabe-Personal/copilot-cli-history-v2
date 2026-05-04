import type { HistorySyncState } from '../hooks/useHistorySync.ts'
import StatusPanel from './StatusPanel.tsx'

interface SessionEmptyStateProps {
  appliedRangeLabel: string
  syncState: HistorySyncState
  isSyncing: boolean
  onSync: () => void | Promise<void>
}

function SessionEmptyState({
  appliedRangeLabel,
  syncState,
  isSyncing,
  onSync,
}: SessionEmptyStateProps) {
  const syncedHint =
    syncState.status === 'synced_empty'
      ? 'この条件では、まだ一致するセッションが見つかっていません。'
      : null

  return (
    <StatusPanel
      variant="empty"
      title="この日付範囲に一致するセッションはありません"
      message={`現在の表示範囲: ${appliedRangeLabel}`}
      action={
        <div className="flex flex-col gap-3">
          {syncedHint != null ? (
            <p className="text-sm leading-6 text-slate-300">{syncedHint}</p>
          ) : null}

          <div>
            <button
              type="button"
              onClick={() => {
                void onSync()
              }}
              disabled={isSyncing}
              className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-cyan-400/20 disabled:bg-cyan-400/5 disabled:text-cyan-100/70"
            >
              {isSyncing ? '履歴を取り込み中...' : '履歴を取り込む'}
            </button>
          </div>
        </div>
      }
    />
  )
}

export default SessionEmptyState

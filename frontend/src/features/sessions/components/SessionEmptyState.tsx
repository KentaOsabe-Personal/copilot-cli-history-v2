import type { HistorySyncState } from '../hooks/useHistorySync.ts'
import StatusPanel from './StatusPanel.tsx'

interface SessionEmptyStateProps {
  appliedRangeLabel: string
  appliedSearchTerm?: string
  syncState: HistorySyncState
  isSyncing: boolean
  onSync: () => void | Promise<void>
  onClearSearch?: () => void | Promise<void>
}

function SessionEmptyState({
  appliedRangeLabel,
  appliedSearchTerm = '',
  syncState,
  isSyncing,
  onSync,
  onClearSearch,
}: SessionEmptyStateProps) {
  const hasSearch = appliedSearchTerm !== ''
  const syncedHint =
    syncState.status === 'synced_empty'
      ? 'この条件では、まだ一致するセッションが見つかっていません。'
      : null
  const title = hasSearch
    ? '検索条件に一致するセッションはありません'
    : 'この日付範囲に一致するセッションはありません'
  const message = hasSearch
    ? `現在の表示条件: ${appliedRangeLabel} / 検索: ${appliedSearchTerm}`
    : `現在の表示範囲: ${appliedRangeLabel}`

  return (
    <StatusPanel
      variant="empty"
      title={title}
      message={message}
      action={
        <div className="flex flex-col gap-3">
          {syncedHint != null ? (
            <p className="text-sm leading-6 text-slate-300">{syncedHint}</p>
          ) : null}

          <div className="flex flex-wrap gap-3">
            {hasSearch && onClearSearch != null ? (
              <button
                type="button"
                onClick={() => {
                  void onClearSearch()
                }}
                className="inline-flex items-center rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-400 hover:bg-white/10"
              >
                検索を解除
              </button>
            ) : null}
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

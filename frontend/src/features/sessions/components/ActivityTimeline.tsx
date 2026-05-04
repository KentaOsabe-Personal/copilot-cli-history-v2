import type { SessionActivity } from '../api/sessionApi.types.ts'
import { formatActivityContent } from '../presentation/timelineContent.ts'
import { formatTimestamp } from '../presentation/formatters.ts'
import IssueList from './IssueList.tsx'
import TimelineContent from './TimelineContent.tsx'

interface ActivityTimelineProps {
  activity: SessionActivity
  rawIncluded: boolean
  rawStatus: 'idle' | 'loading' | 'included' | 'error'
  onRequestRaw: () => void
  stateScopeKey: string
}

function ActivityTimeline({
  activity,
  rawIncluded,
  rawStatus,
  onRequestRaw,
  stateScopeKey,
}: ActivityTimelineProps) {
  if (activity.entries.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-600 bg-slate-900 px-3 py-1 text-xs font-semibold text-slate-200">
          {rawIncluded || rawStatus === 'included' ? 'raw included' : 'raw omitted'}
        </span>
        <button
          type="button"
          onClick={onRequestRaw}
          disabled={rawStatus === 'loading' || rawIncluded}
          className="rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {rawStatus === 'loading' ? 'Raw 取得中' : 'Raw を取得'}
        </button>
      </div>

      {rawStatus === 'error' ? (
        <p className="rounded-3xl border border-amber-400/25 bg-amber-400/10 p-4 text-sm text-amber-100">
          Raw の取得に失敗しました。会話と activity は通常 detail の内容で表示しています。
        </p>
      ) : null}

      <ol className="space-y-4">
        {activity.entries.map((entry) => {
          const content = formatActivityContent(entry)

          return (
            <li
              key={entry.sequence}
              className="rounded-3xl border border-slate-700/70 bg-slate-900/60 p-6 shadow-2xl shadow-slate-950/20"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-lg font-semibold text-white">{`Activity #${entry.sequence}`}</h4>
                <span className="rounded-full bg-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-100">
                  {entry.category}
                </span>
                {entry.mapping_status === 'partial' ? (
                  <span className="rounded-full border border-amber-300/40 bg-amber-300/10 px-2.5 py-1 text-xs font-semibold text-amber-100">
                    partial
                  </span>
                ) : null}
                {entry.raw_type != null ? (
                  <span className="rounded-full bg-slate-950/40 px-2.5 py-1 text-xs font-semibold text-slate-200">
                    {entry.raw_type}
                  </span>
                ) : null}
              </div>

              <dl className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    発生時刻
                  </dt>
                  <dd className="mt-1">{formatTimestamp(content.occurredAt)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Raw
                  </dt>
                  <dd className="mt-1">{content.rawAvailable ? '参照可能' : '参照不可'}</dd>
                </div>
              </dl>

              <div className="mt-4">
                <TimelineContent
                  stateScopeKey={`${stateScopeKey}:activity:${entry.sequence}`}
                  event={{
                    content: null,
                    tool_calls: [],
                    detail: {
                      category: entry.category,
                      title: entry.title,
                      body: entry.summary,
                    },
                  }}
                />
              </div>

              {rawIncluded && entry.raw_payload != null ? (
                <pre className="mt-4 overflow-x-auto whitespace-pre rounded-2xl border border-white/10 bg-slate-950/90 p-4 text-xs text-slate-100">
                  <code>{JSON.stringify(entry.raw_payload, null, 2)}</code>
                </pre>
              ) : null}

              <div className="mt-4">
                <IssueList title="Activity の issue" issues={content.issues} />
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default ActivityTimeline

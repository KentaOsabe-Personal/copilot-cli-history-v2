import { Link } from 'react-router'

import type { SessionSummary } from '../api/sessionApi.types.ts'
import {
  buildSessionMetadataItems,
  buildSessionSummarySignals,
} from '../presentation/formatters.ts'

interface SessionSummaryCardProps {
  session: SessionSummary
}

function SessionSummaryCard({ session }: SessionSummaryCardProps) {
  const metadataItems = buildSessionMetadataItems({
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    workContext: session.work_context,
    selectedModel: session.selected_model,
  })
  const signals = buildSessionSummarySignals({
    hasConversation: session.conversation_summary.has_conversation,
    degraded: session.degraded,
    sourceState: session.source_state,
  })

  return (
    <article className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/20">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="min-w-0 break-all font-mono text-lg font-semibold text-cyan-200">
              {session.id}
            </h3>
            {signals.map((signal) => (
              <span
                key={signal.label}
                className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                  signal.tone === 'warning'
                    ? 'bg-amber-400/15 text-amber-200 ring-1 ring-amber-300/25'
                    : 'bg-slate-700 text-slate-100 ring-1 ring-slate-600'
                }`}
              >
                {signal.label}
              </span>
            ))}
          </div>

          <div className="mt-4 rounded-2xl border border-slate-700/70 bg-slate-950/30 p-4">
            <p className="whitespace-pre-wrap break-words text-sm font-medium text-white">
              {session.conversation_summary.preview ?? '表示できる会話本文はありません'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-slate-300">
              <span className="rounded-full bg-slate-800 px-2.5 py-1">
                {`${session.conversation_summary.message_count} 件の会話`}
              </span>
            </div>
          </div>

          {metadataItems.length > 0 ? (
            <dl className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
              {metadataItems.map((item) => (
                <div key={item.label} className="min-w-0">
                  <dt className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    {item.label}
                  </dt>
                  <dd className="mt-1 break-words">{item.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>

        <div className="shrink-0">
          <Link
            to={`/sessions/${encodeURIComponent(session.id)}`}
            className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20"
            aria-label={`${session.id} を開く`}
          >
            詳細を開く
          </Link>
        </div>
      </div>
    </article>
  )
}

export default SessionSummaryCard

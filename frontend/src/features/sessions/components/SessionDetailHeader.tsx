import { Link } from 'react-router'

import type { SessionDetail } from '../api/sessionApi.types.ts'
import {
  buildSessionMetadataItems,
  buildSessionDetailSignals,
} from '../presentation/formatters.ts'

interface SessionDetailHeaderProps {
  detail: SessionDetail
}

function SessionDetailHeader({ detail }: SessionDetailHeaderProps) {
  const metadataItems = buildSessionMetadataItems({
    createdAt: detail.created_at,
    updatedAt: detail.updated_at,
    workContext: detail.work_context,
    selectedModel: detail.selected_model,
  })
  const signals = buildSessionDetailSignals({
    degraded: detail.degraded,
    sourceState: detail.source_state,
  })

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/20">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="min-w-0 break-all font-mono text-xl font-semibold text-cyan-200">
              {detail.id}
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
            to="/"
            className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20"
          >
            セッション一覧へ戻る
          </Link>
        </div>
      </div>
    </section>
  )
}

export default SessionDetailHeader

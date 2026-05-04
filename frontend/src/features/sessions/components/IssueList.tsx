import type { SessionIssue } from '../api/sessionApi.types.ts'
import { formatIssueMetadata } from '../presentation/formatters.ts'

interface IssueListProps {
  title?: string
  issues: readonly SessionIssue[]
}

function IssueList({ title, issues }: IssueListProps) {
  if (issues.length === 0) {
    return null
  }

  return (
    <section className="rounded-3xl border border-amber-400/25 bg-amber-400/10 p-6 text-amber-50">
      {title != null ? <h3 className="text-lg font-semibold text-amber-100">{title}</h3> : null}
      <ul className="mt-4 space-y-4">
        {issues.map((issue, index) => {
          const metadata = formatIssueMetadata(issue)

          return (
            <li key={`${issue.code}-${issue.event_sequence ?? 'session'}-${index}`} className="space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                <span className="rounded-full bg-amber-200/15 px-2.5 py-1 text-amber-100">
                  {metadata.severityLabel}
                </span>
                <span className="rounded-full bg-slate-950/30 px-2.5 py-1 text-amber-50">
                  {metadata.scopeLabel}
                </span>
                {metadata.locationLabel != null ? (
                  <span className="rounded-full bg-slate-950/30 px-2.5 py-1 text-amber-50">
                    {metadata.locationLabel}
                  </span>
                ) : null}
              </div>
              <p className="whitespace-pre-wrap break-words text-sm leading-6 text-amber-50">
                {issue.message}
              </p>
              {issue.source_path != null ? (
                <p className="break-all font-mono text-xs text-amber-100/80">{issue.source_path}</p>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export default IssueList

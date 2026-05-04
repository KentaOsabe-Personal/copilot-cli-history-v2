import { useState } from 'react'

import type { SessionTimelineEvent } from '../api/sessionApi.types.ts'
import { formatTimelineContent } from '../presentation/timelineContent.ts'

interface TimelineContentProps {
  stateScopeKey: string
  event: Pick<SessionTimelineEvent, 'content' | 'tool_calls' | 'detail'>
}

function TimelineContent({ event, stateScopeKey }: TimelineContentProps) {
  const { blocks } = formatTimelineContent(event)
  const [toolDisclosureState, setToolDisclosureState] = useState<{
    scopeKey: string
    expandedTools: Readonly<Record<string, boolean>>
  }>({
    scopeKey: '',
    expandedTools: {},
  })
  const expandedTools =
    toolDisclosureState.scopeKey === stateScopeKey ? toolDisclosureState.expandedTools : {}

  if (blocks.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, index) => {
        if (block.kind === 'tool_hint') {
          const toolName = block.name ?? 'unknown tool'
          const toolKey = `tool-${index}`
          const argumentsContentId = `${stateScopeKey}-${toolKey}-arguments`
          const hasArgumentsPreview = block.argumentsPreview != null
          const isExpanded = expandedTools[toolKey] ?? !block.argumentsDefaultCollapsed

          return (
            <section
              key={toolKey}
              role="group"
              aria-label={`tool call ${toolName}`}
              className="rounded-2xl border border-cyan-400/30 bg-cyan-400/10 p-4 text-cyan-50"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-100/80">
                      ツール呼び出し
                    </p>
                    {block.status === 'partial' ? (
                      <span className="rounded-full border border-amber-300/40 bg-amber-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100">
                        partial
                      </span>
                    ) : null}
                    {block.isTruncated ? (
                      <span className="rounded-full border border-cyan-200/30 bg-cyan-50/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-50">
                        truncated
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-2 font-mono text-sm text-cyan-100">{toolName}</p>
                </div>

                {hasArgumentsPreview ? (
                  <button
                    type="button"
                    className="rounded-full border border-cyan-200/30 bg-cyan-50/10 px-3 py-1 text-xs font-semibold text-cyan-50 transition hover:border-cyan-100/60 hover:bg-cyan-50/20"
                    aria-controls={argumentsContentId}
                    aria-expanded={isExpanded}
                    onClick={() => {
                      setToolDisclosureState((current) => {
                        const currentTools =
                          current.scopeKey === stateScopeKey ? current.expandedTools : {}

                        return {
                          scopeKey: stateScopeKey,
                          expandedTools: {
                            ...currentTools,
                            [toolKey]: !isExpanded,
                          },
                        }
                      })
                    }}
                  >
                    {isExpanded ? 'arguments を隠す' : 'arguments を表示'}
                  </button>
                ) : null}
              </div>

                <div id={argumentsContentId} hidden={!hasArgumentsPreview || !isExpanded}>
                  {hasArgumentsPreview && isExpanded ? (
                    <pre className="mt-3 overflow-x-auto whitespace-pre rounded-xl bg-slate-950/50 p-3 text-xs text-cyan-50">
                      <code>{block.argumentsPreview}</code>
                    </pre>
                  ) : null}
                </div>
            </section>
          )
        }

        if (block.kind === 'code') {
          return (
            <pre
              key={`code-${index}`}
              className="overflow-x-auto whitespace-pre rounded-2xl border border-white/10 bg-slate-950/90 p-4 text-sm text-slate-100"
            >
              <code>{block.code}</code>
            </pre>
          )
        }

        if (block.kind === 'detail') {
          return (
            <section
              key={`detail-${index}`}
              className="rounded-2xl border border-slate-700 bg-slate-950/40 p-4 text-slate-100"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                詳細イベント
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-slate-600 bg-slate-800/80 px-2.5 py-1 text-[11px] font-semibold text-slate-200">
                  {block.category}
                </span>
                <p className="text-sm font-medium text-slate-100">{block.title}</p>
              </div>
              {block.body != null ? (
                <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
                  {block.body}
                </p>
              ) : null}
            </section>
          )
        }

        return (
          <p
            key={`text-${index}`}
            className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-100"
          >
            {block.text}
          </p>
        )
      })}
    </div>
  )
}

export default TimelineContent

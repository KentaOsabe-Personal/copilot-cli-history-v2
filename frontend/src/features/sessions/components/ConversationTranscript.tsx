import { useState } from 'react'

import type { SessionConversation } from '../api/sessionApi.types.ts'
import {
  formatConversationEntryContent,
  shouldDefaultHideConversationEntryModel,
} from '../presentation/conversationContent.ts'
import { formatTimestamp } from '../presentation/formatters.ts'
import IssueList from './IssueList.tsx'
import TimelineContent from './TimelineContent.tsx'

interface ConversationTranscriptProps {
  conversation: SessionConversation
  stateScopeKey: string
}

function ConversationTranscript({ conversation, stateScopeKey }: ConversationTranscriptProps) {
  const [visibilityState, setVisibilityState] = useState<{
    scopeKey: string
    visibleEntries: Readonly<Record<number, boolean>>
  }>({
    scopeKey: '',
    visibleEntries: {},
  })
  const visibleEntries =
    visibilityState.scopeKey === stateScopeKey ? visibilityState.visibleEntries : {}

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold text-white">会話</h3>
          <p className="mt-1 text-sm text-slate-400">
            {conversation.message_count > 0
              ? `${conversation.message_count} 件の user / assistant 発話`
              : '表示できる会話本文はありません'}
          </p>
        </div>
      </div>

      {conversation.entries.length === 0 ? (
        <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 text-slate-300">
          <p className="text-base font-medium text-white">表示できる会話本文はありません</p>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            このセッションには user / assistant の本文がないか、会話として表示できる event がありません。
          </p>
        </div>
      ) : (
        <ol className="space-y-4">
          {conversation.entries.map((entry) => {
            const content = formatConversationEntryContent(entry)
            const isVisible =
              visibleEntries[entry.sequence] ?? !shouldDefaultHideConversationEntryModel(content)
            const entryContentId = `${stateScopeKey}-entry-${entry.sequence}-content`
            const roleCardClass =
              entry.role === 'assistant'
                ? 'border-cyan-300/35 bg-cyan-950/25 shadow-cyan-950/20'
                : 'border-emerald-300/35 bg-emerald-950/20 shadow-emerald-950/20'
            const roleAccentClass = entry.role === 'assistant' ? 'bg-cyan-300' : 'bg-emerald-300'

            return (
              <li
                key={entry.sequence}
                data-testid={`conversation-entry-${entry.sequence}`}
                data-role={entry.role}
                className={`relative overflow-hidden rounded-3xl border p-6 shadow-2xl ${roleCardClass}`}
              >
                <div className={`absolute inset-y-0 left-0 w-1 ${roleAccentClass}`} aria-hidden="true" />
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="text-lg font-semibold text-white">{`発話 #${entry.sequence}`}</h4>
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                        entry.role === 'assistant'
                          ? 'bg-cyan-400/10 text-cyan-100'
                          : 'bg-emerald-400/10 text-emerald-100'
                      }`}
                    >
                      {entry.role}
                    </span>
                    {entry.degraded ? (
                      <span className="rounded-full border border-amber-300/40 bg-amber-300/10 px-2.5 py-1 text-xs font-semibold text-amber-100">
                        partial
                      </span>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 transition hover:border-white/30 hover:bg-white/10"
                    aria-controls={entryContentId}
                    aria-expanded={isVisible}
                    onClick={() => {
                      setVisibilityState((current) => {
                        const currentEntries =
                          current.scopeKey === stateScopeKey ? current.visibleEntries : {}

                        return {
                          scopeKey: stateScopeKey,
                          visibleEntries: {
                            ...currentEntries,
                            [entry.sequence]: !isVisible,
                          },
                        }
                      })
                    }}
                  >
                    {isVisible ? `発話 #${entry.sequence} を非表示` : `発話 #${entry.sequence} を表示`}
                  </button>
                </div>

                <p className="mt-3 text-sm text-slate-400">{formatTimestamp(content.occurredAt)}</p>

                <div id={entryContentId} hidden={!isVisible}>
                  {isVisible ? (
                    <>
                      <div className="mt-4">
                        <TimelineContent
                          stateScopeKey={`${stateScopeKey}:entry:${entry.sequence}`}
                          event={{
                            content: entry.content,
                            tool_calls: entry.tool_calls,
                            detail: null,
                          }}
                        />
                      </div>

                      <div className="mt-4">
                        <IssueList title="発話の issue" issues={content.issues} />
                      </div>
                    </>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

export default ConversationTranscript

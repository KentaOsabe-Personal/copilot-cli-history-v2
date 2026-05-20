import { useState } from 'react'

import {
  normalizeSearchTerm,
  validateSearchTerm,
} from '../presentation/sessionIndexCriteria.ts'

interface SessionSearchFormProps {
  appliedSearchTerm: string
  appliedCriteriaLabel: string
  isApplying: boolean
  backendErrorMessage: string | null
  onApplySearch: (searchTerm: string) => void | Promise<void>
  onClearSearch: () => void | Promise<void>
}

function SessionSearchForm({
  appliedSearchTerm,
  appliedCriteriaLabel,
  isApplying,
  backendErrorMessage,
  onApplySearch,
  onClearSearch,
}: SessionSearchFormProps) {
  const [draftState, setDraftState] = useState(() => ({
    appliedSearchTerm,
    draftSearchTerm: appliedSearchTerm,
    submittedValidationMessage: null as string | null,
  }))
  const isDraftForCurrentAppliedSearch = draftState.appliedSearchTerm === appliedSearchTerm
  const draftSearchTerm = isDraftForCurrentAppliedSearch
    ? draftState.draftSearchTerm
    : appliedSearchTerm
  const submittedValidationMessage = isDraftForCurrentAppliedSearch
    ? draftState.submittedValidationMessage
    : null
  const validation = validateSearchTerm(draftSearchTerm)
  const validationMessage =
    backendErrorMessage ?? submittedValidationMessage

  return (
    <form
      className="flex flex-col gap-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4"
      onSubmit={(event) => {
        event.preventDefault()

        if (isApplying) {
          return
        }

        if (validation.kind === 'invalid') {
          setDraftState({
            appliedSearchTerm,
            draftSearchTerm,
            submittedValidationMessage: validation.message,
          })

          return
        }

        setDraftState({
          appliedSearchTerm,
          draftSearchTerm,
          submittedValidationMessage: null,
        })
        void onApplySearch(normalizeSearchTerm(draftSearchTerm))
      }}
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-white">検索語で絞り込む</h3>
        <p className="text-sm text-slate-300">
          現在の検索条件: {appliedCriteriaLabel}
        </p>
      </div>

      <label className="flex flex-col gap-2 text-sm text-slate-200">
        <span>検索語</span>
        <input
          type="search"
          value={draftSearchTerm}
          onChange={(event) => {
            setDraftState({
              appliedSearchTerm,
              draftSearchTerm: event.target.value,
              submittedValidationMessage: null,
            })
          }}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white outline-none transition focus:border-cyan-400"
        />
      </label>

      {validationMessage != null ? (
        <p role="alert" className="text-sm text-rose-300">
          {validationMessage}
        </p>
      ) : (
        <p className="text-sm text-slate-400">
          会話本文、会話 preview、issue、実行ディレクトリの内容を検索します。
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-3">
        {appliedSearchTerm !== '' ? (
          <button
            type="button"
            onClick={() => {
              setDraftState({
                appliedSearchTerm,
                draftSearchTerm,
                submittedValidationMessage: null,
              })
              void onClearSearch()
            }}
            disabled={isApplying}
            className="inline-flex items-center rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-400 hover:bg-white/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-400"
          >
            検索を解除
          </button>
        ) : null}
        <button
          type="submit"
          disabled={isApplying}
          className="inline-flex items-center rounded-lg border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-cyan-400/20 disabled:bg-cyan-400/5 disabled:text-cyan-100/70"
        >
          {isApplying ? '検索中...' : '検索する'}
        </button>
      </div>
    </form>
  )
}

export default SessionSearchForm

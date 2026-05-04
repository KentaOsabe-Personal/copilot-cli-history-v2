import {
  formatRangeLabel,
  validateRange,
  type SessionDateRangeDraft,
} from '../presentation/sessionDateFilter.ts'

interface SessionDateFilterFormProps {
  draftRange: SessionDateRangeDraft
  appliedRange: SessionDateRangeDraft
  isApplying: boolean
  onDraftChange: (range: SessionDateRangeDraft) => void
  onApply: (range: SessionDateRangeDraft) => void | Promise<void>
}

function SessionDateFilterForm({
  draftRange,
  appliedRange,
  isApplying,
  onDraftChange,
  onApply,
}: SessionDateFilterFormProps) {
  const validation = validateRange(draftRange)
  const isInvalid = validation.kind === 'invalid'

  return (
    <form
      className="flex flex-col gap-4 rounded-3xl border border-slate-800 bg-slate-950/40 p-4"
      onSubmit={(event) => {
        event.preventDefault()

        if (isInvalid || isApplying) {
          return
        }

        void onApply(draftRange)
      }}
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-white">日付範囲で絞り込む</h3>
        <p className="text-sm text-slate-300">
          現在の表示範囲: {formatRangeLabel(appliedRange)}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          <span>開始日</span>
          <input
            type="date"
            value={draftRange.from}
            onChange={(event) => {
              onDraftChange({
                ...draftRange,
                from: event.target.value,
              })
            }}
            className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-white outline-none transition focus:border-cyan-400"
          />
        </label>

        <label className="flex flex-col gap-2 text-sm text-slate-200">
          <span>終了日</span>
          <input
            type="date"
            value={draftRange.to}
            onChange={(event) => {
              onDraftChange({
                ...draftRange,
                to: event.target.value,
              })
            }}
            className="rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-white outline-none transition focus:border-cyan-400"
          />
        </label>
      </div>

      {validation.kind === 'invalid' ? (
        <p role="alert" className="text-sm text-rose-300">
          {validation.message}
        </p>
      ) : (
        <p className="text-sm text-slate-400">
          両方空のまま適用すると、直近 7 日の表示に戻ります。
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isInvalid || isApplying}
          className="inline-flex items-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-cyan-400/20 disabled:bg-cyan-400/5 disabled:text-cyan-100/70"
        >
          {isApplying ? '適用中...' : '適用する'}
        </button>
      </div>
    </form>
  )
}

export default SessionDateFilterForm

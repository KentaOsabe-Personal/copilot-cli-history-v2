import { useEffect, useRef } from 'react'

import type {
  SessionDirectoryTab,
  SessionDirectoryTabKey,
} from '../presentation/sessionDirectoryTabs.ts'

interface SessionDirectoryTabsProps {
  tabs: readonly SessionDirectoryTab[]
  selectedKey: SessionDirectoryTabKey
  panelId: string
  getTabId: (key: SessionDirectoryTabKey) => string
  onSelect: (key: SessionDirectoryTabKey) => void
}

function SessionDirectoryTabs({
  tabs,
  selectedKey,
  panelId,
  getTabId,
  onSelect,
}: SessionDirectoryTabsProps) {
  const selectedTabRef = useRef<HTMLButtonElement | null>(null)
  const shouldFocusSelectedTabRef = useRef(false)
  const allTab = tabs.find((tab) => tab.kind === 'all')
  const totalCount = allTab?.count ?? 0

  useEffect(() => {
    if (shouldFocusSelectedTabRef.current) {
      selectedTabRef.current?.focus()
      shouldFocusSelectedTabRef.current = false
    }
  }, [selectedKey])

  return (
    <div className="max-w-full overflow-x-auto">
      <div
        role="tablist"
        aria-label={`作業ディレクトリ別セッション一覧タブ、全 ${totalCount} 件`}
        className="flex w-max max-w-full min-w-0 gap-2"
      >
        {tabs.map((tab, index) => {
          const isSelected = tab.key === selectedKey
          const tabLabel = buildTabDisplayLabel(tab)

          return (
            <button
              key={tab.key}
              ref={isSelected ? selectedTabRef : null}
              id={getTabId(tab.key)}
              type="button"
              role="tab"
              aria-selected={isSelected}
              aria-controls={panelId}
              aria-label={buildTabAriaLabel(tab)}
              tabIndex={isSelected ? 0 : -1}
              title={tab.fullPath ?? undefined}
              onClick={() => {
                onSelect(tab.key)
              }}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
                  return
                }

                event.preventDefault()
                const direction = event.key === 'ArrowRight' ? 1 : -1
                const nextIndex = (index + direction + tabs.length) % tabs.length
                shouldFocusSelectedTabRef.current = true
                onSelect(tabs[nextIndex].key)
              }}
              className={`inline-flex max-w-64 shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:ring-offset-2 focus:ring-offset-slate-950 ${
                isSelected
                  ? 'border-cyan-300 bg-cyan-300/15 text-cyan-50'
                  : 'border-slate-700 bg-slate-900/80 text-slate-200 hover:border-slate-500 hover:bg-slate-800'
              }`}
            >
              <span className="min-w-0 truncate">{tabLabel}</span>
              <span className="shrink-0 rounded-full bg-slate-950/70 px-2 py-0.5 text-xs text-slate-200">
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function buildTabDisplayLabel(tab: SessionDirectoryTab): string {
  if (tab.contextLabel == null) {
    return tab.label
  }

  return `${tab.contextLabel} / ${tab.label}`
}

function buildTabAriaLabel(tab: SessionDirectoryTab): string {
  const baseLabel = `${buildTabDisplayLabel(tab)}、${tab.count} 件`

  if (tab.kind === 'directory' && tab.fullPath != null) {
    return `${baseLabel}、完全パス ${tab.fullPath}`
  }

  if (tab.kind === 'unset') {
    return `${baseLabel}、作業ディレクトリ未設定`
  }

  return baseLabel
}

export default SessionDirectoryTabs

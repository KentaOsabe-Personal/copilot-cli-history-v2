import type { SessionIssue, SessionSourceState, WorkContext } from '../api/sessionApi.types.ts'

const MISSING_TIMESTAMP_LABEL = '時刻不明'
const JST_TIME_ZONE = 'Asia/Tokyo'
const JST_SUFFIX = 'JST'
const JST_TIMESTAMP_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: JST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  hourCycle: 'h23',
})

const ISSUE_SEVERITY_LABELS: Record<string, string> = {
  error: 'エラー',
  warning: '警告',
  info: '情報',
}

const ISSUE_SCOPE_LABELS: Record<string, string> = {
  session: 'セッション',
  event: 'イベント',
}

export function formatTimestamp(value: string | null): string {
  if (value == null) {
    return MISSING_TIMESTAMP_LABEL
  }

  const timestamp = new Date(value)

  if (Number.isNaN(timestamp.getTime())) {
    return value
  }

  const parts = JST_TIMESTAMP_FORMATTER.formatToParts(timestamp)

  const partValues = Object.fromEntries(parts.map((part) => [part.type, part.value]))

  return `${partValues.year}-${partValues.month}-${partValues.day} ${partValues.hour}:${partValues.minute}:${partValues.second} ${JST_SUFFIX}`
}

export interface MetadataDisplayItem {
  label: '更新日時' | '作業コンテキスト' | 'モデル'
  value: string
}

export interface SessionSignalBadge {
  label: string
  tone: 'neutral' | 'warning'
}

export function getDisplayableWorkContext(workContext: WorkContext): string | null {
  const repository = normalizeText(workContext.repository)
  const branch = normalizeText(workContext.branch)
  const cwd = normalizeText(workContext.cwd)
  const gitRoot = normalizeText(workContext.git_root)

  if (repository != null && branch != null) {
    return `${repository} @ ${branch}`
  }

  return repository ?? cwd ?? gitRoot
}

export function getDisplayableModel(value: string | null): string | null {
  return normalizeText(value)
}

export function buildSessionMetadataItems(input: {
  createdAt: string | null
  updatedAt: string | null
  workContext: WorkContext
  selectedModel: string | null
}): readonly MetadataDisplayItem[] {
  const items: MetadataDisplayItem[] = [
    {
      label: '更新日時',
      value: formatTimestamp(input.updatedAt ?? input.createdAt),
    },
  ]
  const workContext = getDisplayableWorkContext(input.workContext)
  const model = getDisplayableModel(input.selectedModel)

  if (workContext != null) {
    items.push({
      label: '作業コンテキスト',
      value: workContext,
    })
  }

  if (model != null) {
    items.push({
      label: 'モデル',
      value: model,
    })
  }

  return items
}

export function formatDegradedLabel(degraded: boolean): string {
  return degraded ? '一部欠損あり' : '正常'
}

export function formatSourceStateLabel(sourceState: SessionSourceState): string {
  if (sourceState === 'workspace_only') {
    return 'workspace-only'
  }

  return sourceState
}

export function buildSessionSummarySignals(input: {
  hasConversation: boolean
  degraded: boolean
  sourceState: SessionSourceState
}): readonly SessionSignalBadge[] {
  const badges: SessionSignalBadge[] = []

  if (!input.hasConversation) {
    badges.push({
      label: input.sourceState === 'workspace_only' ? 'workspace-only' : 'metadata-only',
      tone: input.sourceState === 'workspace_only' ? 'warning' : 'neutral',
    })
  }

  const constraintBadge = buildSessionConstraintBadge(input)

  if (constraintBadge != null && !badges.some((badge) => badge.label === constraintBadge.label)) {
    badges.push(constraintBadge)
  }

  return badges
}

export function buildSessionDetailSignals(input: {
  degraded: boolean
  sourceState: SessionSourceState
}): readonly SessionSignalBadge[] {
  const constraintBadge = buildSessionConstraintBadge(input)

  return constraintBadge == null ? [] : [constraintBadge]
}

export function formatIssueMetadata(
  issue: Pick<SessionIssue, 'severity' | 'scope' | 'event_sequence'>,
): {
  severityLabel: string
  scopeLabel: string
  locationLabel: string | null
} {
  const scopeLabel = ISSUE_SCOPE_LABELS[issue.scope] ?? issue.scope

  return {
    severityLabel: ISSUE_SEVERITY_LABELS[issue.severity] ?? issue.severity,
    scopeLabel,
    locationLabel:
      issue.event_sequence != null
        ? `イベント #${issue.event_sequence}`
        : issue.scope === 'session'
          ? 'セッション全体'
          : scopeLabel,
  }
}

function normalizeText(value: string | null): string | null {
  const normalized = value?.trim()

  return normalized != null && normalized.length > 0 ? normalized : null
}

function buildSessionConstraintBadge(input: {
  degraded: boolean
  sourceState: SessionSourceState
}): SessionSignalBadge | null {
  if (input.degraded || input.sourceState === 'degraded') {
    return {
      label: '一部欠損あり',
      tone: 'warning',
    }
  }

  if (input.sourceState === 'workspace_only') {
    return {
      label: 'workspace-only',
      tone: 'warning',
    }
  }

  return null
}

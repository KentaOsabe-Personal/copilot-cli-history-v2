import type { SessionSummary } from '../api/sessionApi.types.ts'

export type SessionDirectoryTabKey = 'all' | 'unset' | `cwd:${string}`

export interface SessionDirectoryTab {
  key: SessionDirectoryTabKey
  kind: 'all' | 'directory' | 'unset'
  label: string
  contextLabel: string | null
  fullPath: string | null
  count: number
}

export interface SessionDirectoryTabBuildResult {
  tabs: readonly SessionDirectoryTab[]
}

interface DirectoryGroup {
  cwd: string
  count: number
  label: string
  parentSegments: readonly string[]
}

export function buildSessionDirectoryTabs(
  sessions: readonly SessionSummary[],
): SessionDirectoryTabBuildResult {
  const directoryGroups = new Map<string, DirectoryGroup>()
  let unsetCount = 0

  for (const session of sessions) {
    const cwd = normalizeCwd(session.work_context.cwd)

    if (cwd == null) {
      unsetCount += 1
      continue
    }

    const existingGroup = directoryGroups.get(cwd)

    if (existingGroup != null) {
      existingGroup.count += 1
      continue
    }

    const pathParts = splitPathParts(cwd)
    const label = pathParts.at(-1) ?? cwd

    directoryGroups.set(cwd, {
      cwd,
      count: 1,
      label,
      parentSegments: pathParts.slice(0, -1),
    })
  }

  const groups = [...directoryGroups.values()]
  const contextLabels = buildContextLabels(groups)
  const tabs: SessionDirectoryTab[] = [
    {
      key: 'all',
      kind: 'all',
      label: 'すべて',
      contextLabel: null,
      fullPath: null,
      count: sessions.length,
    },
  ]

  for (const group of groups) {
    tabs.push({
      key: buildDirectoryTabKey(group.cwd),
      kind: 'directory',
      label: group.label,
      contextLabel: contextLabels.get(group.cwd) ?? null,
      fullPath: group.cwd,
      count: group.count,
    })
  }

  if (unsetCount > 0) {
    tabs.push({
      key: 'unset',
      kind: 'unset',
      label: 'ディレクトリ未設定',
      contextLabel: null,
      fullPath: null,
      count: unsetCount,
    })
  }

  return { tabs }
}

export function getSessionsForDirectoryTab(
  sessions: readonly SessionSummary[],
  selectedKey: SessionDirectoryTabKey,
): readonly SessionSummary[] {
  if (selectedKey === 'all') {
    return sessions
  }

  if (selectedKey === 'unset') {
    return sessions.filter((session) => normalizeCwd(session.work_context.cwd) == null)
  }

  const selectedCwd = selectedKey.slice('cwd:'.length)

  return sessions.filter((session) => normalizeCwd(session.work_context.cwd) === selectedCwd)
}

export function coerceDirectoryTabKey(
  selectedKey: SessionDirectoryTabKey,
  tabs: readonly SessionDirectoryTab[],
): SessionDirectoryTabKey {
  if (tabs.some((tab) => tab.key === selectedKey)) {
    return selectedKey
  }

  return 'all'
}

function buildDirectoryTabKey(cwd: string): SessionDirectoryTabKey {
  return `cwd:${cwd}`
}

function normalizeCwd(value: string | null): string | null {
  const normalized = value?.trim()

  if (normalized == null || normalized.length === 0) {
    return null
  }

  return normalized
}

function splitPathParts(path: string): readonly string[] {
  const parts = path.split('/').filter((part) => part.length > 0)

  if (parts.length > 0) {
    return parts
  }

  return [path]
}

function buildContextLabels(groups: readonly DirectoryGroup[]): Map<string, string> {
  const contextLabels = new Map<string, string>()
  const groupsByLabel = new Map<string, DirectoryGroup[]>()

  for (const group of groups) {
    const labelGroups = groupsByLabel.get(group.label)

    if (labelGroups == null) {
      groupsByLabel.set(group.label, [group])
      continue
    }

    labelGroups.push(group)
  }

  for (const duplicateGroup of groupsByLabel.values()) {
    if (duplicateGroup.length < 2) {
      continue
    }

    for (const group of duplicateGroup) {
      contextLabels.set(group.cwd, findUniqueParentContext(group, duplicateGroup))
    }
  }

  return contextLabels
}

function findUniqueParentContext(
  targetGroup: DirectoryGroup,
  duplicateGroups: readonly DirectoryGroup[],
): string {
  const maxParentDepth = Math.max(...duplicateGroups.map((group) => group.parentSegments.length))

  for (let depth = 1; depth <= maxParentDepth; depth += 1) {
    const candidate = buildParentSuffix(targetGroup.parentSegments, depth)

    if (candidate.length === 0) {
      continue
    }

    const isUnique = duplicateGroups.every((group) => {
      if (group.cwd === targetGroup.cwd) {
        return true
      }

      return buildParentSuffix(group.parentSegments, depth) !== candidate
    })

    if (isUnique) {
      return candidate
    }
  }

  return targetGroup.parentSegments.join('/')
}

function buildParentSuffix(parentSegments: readonly string[], depth: number): string {
  return parentSegments.slice(Math.max(parentSegments.length - depth, 0)).join('/')
}

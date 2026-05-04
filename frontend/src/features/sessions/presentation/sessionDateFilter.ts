import type { SessionIndexQuery } from '../api/sessionApi.types.ts'

const JST_TIME_ZONE = 'Asia/Tokyo'
const RANGE_INVALID_MESSAGE = '開始日は終了日以前にしてください。'
const DEFAULT_RANGE_LABEL = '直近 7 日'
const JST_DATE_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: JST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

export interface SessionDateRangeDraft {
  from: string
  to: string
}

export type SessionDateRangeValidation =
  | { kind: 'valid' }
  | { kind: 'invalid'; field: 'range'; message: string }

export function buildDefaultRange(now: Date = new Date()): SessionDateRangeDraft {
  const today = toJstDateString(now)

  return {
    from: shiftDateString(today, -6),
    to: today,
  }
}

export function resolveAppliedRange(
  range: SessionDateRangeDraft,
  now: Date = new Date(),
): SessionDateRangeDraft {
  if (range.from === '' && range.to === '') {
    return buildDefaultRange(now)
  }

  return range
}

export function validateRange(range: SessionDateRangeDraft): SessionDateRangeValidation {
  if (range.from !== '' && range.to !== '' && range.from > range.to) {
    return {
      kind: 'invalid',
      field: 'range',
      message: RANGE_INVALID_MESSAGE,
    }
  }

  return { kind: 'valid' }
}

export function toSessionIndexQuery(range: SessionDateRangeDraft): SessionIndexQuery {
  const query: SessionIndexQuery = {}

  if (range.from !== '') {
    query.from = `${range.from}T00:00:00+09:00`
  }

  if (range.to !== '') {
    query.to = `${range.to}T23:59:59.999999+09:00`
  }

  return query
}

export function formatRangeLabel(range: SessionDateRangeDraft): string {
  if (range.from !== '' && range.to !== '') {
    return `${range.from} 〜 ${range.to}`
  }

  if (range.from !== '') {
    return `${range.from} 以降`
  }

  if (range.to !== '') {
    return `${range.to} 以前`
  }

  return DEFAULT_RANGE_LABEL
}

export function buildQueryKey(range: SessionDateRangeDraft): string {
  return `from=${range.from}|to=${range.to}`
}

function toJstDateString(value: Date): string {
  const parts = JST_DATE_FORMATTER.formatToParts(value)
  const partValues = Object.fromEntries(parts.map((part) => [part.type, part.value]))

  return `${partValues.year}-${partValues.month}-${partValues.day}`
}

function shiftDateString(value: string, offsetDays: number): string {
  const [year, month, day] = value.split('-').map(Number)
  const shifted = new Date(Date.UTC(year, month - 1, day + offsetDays))

  return [
    shifted.getUTCFullYear(),
    String(shifted.getUTCMonth() + 1).padStart(2, '0'),
    String(shifted.getUTCDate()).padStart(2, '0'),
  ].join('-')
}

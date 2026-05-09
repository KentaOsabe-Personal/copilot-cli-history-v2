import type { SessionIndexQuery } from '../api/sessionApi.types.ts'
import {
  buildQueryKey as buildRangeQueryKey,
  formatRangeLabel,
  toSessionIndexQuery as toRangeSessionIndexQuery,
  type SessionDateRangeDraft,
} from './sessionDateFilter.ts'

const SEARCH_INVALID_CONTROL_MESSAGE = '検索語に使用できない制御文字が含まれています。'
const SEARCH_TOO_LONG_MESSAGE = '検索語は 200 文字以内で入力してください。'
export const SEARCH_MAX_LENGTH = 200

export interface SessionIndexCriteria {
  range: SessionDateRangeDraft
  searchTerm: string
}

export type SessionSearchValidation =
  | { kind: 'valid' }
  | { kind: 'invalid'; field: 'search'; message: string }

export function normalizeSearchTerm(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

export function validateSearchTerm(value: string): SessionSearchValidation {
  if (hasDisplayHostileControlCharacter(value)) {
    return {
      kind: 'invalid',
      field: 'search',
      message: SEARCH_INVALID_CONTROL_MESSAGE,
    }
  }

  if (normalizeSearchTerm(value).length > SEARCH_MAX_LENGTH) {
    return {
      kind: 'invalid',
      field: 'search',
      message: SEARCH_TOO_LONG_MESSAGE,
    }
  }

  return { kind: 'valid' }
}

export function toSessionIndexQuery(criteria: SessionIndexCriteria): SessionIndexQuery {
  const query = toRangeSessionIndexQuery(criteria.range)
  const normalizedSearchTerm = normalizeSearchTerm(criteria.searchTerm)

  if (normalizedSearchTerm !== '') {
    query.search = normalizedSearchTerm
  }

  return query
}

export function buildCriteriaKey(criteria: SessionIndexCriteria): string {
  const normalizedSearchTerm = normalizeSearchTerm(criteria.searchTerm)

  if (normalizedSearchTerm === '') {
    return `${buildRangeQueryKey(criteria.range)}|search=`
  }

  return `${buildRangeQueryKey(criteria.range)}|search=${encodeURIComponent(normalizedSearchTerm)}`
}

export function formatCriteriaLabel(criteria: SessionIndexCriteria): string {
  const rangeLabel = formatRangeLabel(criteria.range)
  const normalizedSearchTerm = normalizeSearchTerm(criteria.searchTerm)

  if (normalizedSearchTerm === '') {
    return rangeLabel
  }

  return `${rangeLabel} / 検索: ${normalizedSearchTerm}`
}

function hasDisplayHostileControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0)

    return (
      codePoint != null &&
      ((codePoint >= 0x00 && codePoint <= 0x08) ||
        codePoint === 0x0b ||
        codePoint === 0x0c ||
        (codePoint >= 0x0e && codePoint <= 0x1f) ||
        codePoint === 0x7f)
    )
  })
}

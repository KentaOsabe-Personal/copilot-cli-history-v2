import { describe, expect, it } from 'vitest'

import {
  buildCriteriaKey,
  formatCriteriaLabel,
  normalizeSearchTerm,
  toSessionIndexQuery,
  validateSearchTerm,
  type SessionIndexCriteria,
} from '../../../../src/features/sessions/presentation/sessionIndexCriteria.ts'

const RANGE = {
  from: '2026-04-28',
  to: '2026-05-04',
} as const

describe('sessionIndexCriteria', () => {
  it('builds the API query from date range and normalized search term', () => {
    const criteria: SessionIndexCriteria = {
      range: RANGE,
      searchTerm: '  apply   patch\nfailure  ',
    }

    expect(toSessionIndexQuery(criteria)).toEqual({
      from: '2026-04-28T00:00:00+09:00',
      to: '2026-05-04T23:59:59.999999+09:00',
      search: 'apply patch failure',
    })
  })

  it('omits blank search terms while keeping date range', () => {
    expect(toSessionIndexQuery({ range: RANGE, searchTerm: ' \t\n ' })).toEqual({
      from: '2026-04-28T00:00:00+09:00',
      to: '2026-05-04T23:59:59.999999+09:00',
    })
  })

  it('uses the same normalized search term for criteria keys and labels', () => {
    const criteria: SessionIndexCriteria = {
      range: RANGE,
      searchTerm: '  gpt-5   tokenizer  ',
    }

    expect(buildCriteriaKey(criteria)).toBe('from=2026-04-28|to=2026-05-04|search=gpt-5%20tokenizer')
    expect(formatCriteriaLabel(criteria)).toBe('2026-04-28 〜 2026-05-04 / 検索: gpt-5 tokenizer')
  })

  it('validates search terms with the backend maximum length and control-character rules', () => {
    expect(validateSearchTerm('a'.repeat(200))).toEqual({ kind: 'valid' })
    expect(validateSearchTerm('a'.repeat(201))).toEqual({
      kind: 'invalid',
      field: 'search',
      message: '検索語は 200 文字以内で入力してください。',
    })
    expect(validateSearchTerm('hello\u0000world')).toEqual({
      kind: 'invalid',
      field: 'search',
      message: '検索語に使用できない制御文字が含まれています。',
    })
  })

  it('normalizes blank and spaced search terms consistently', () => {
    expect(normalizeSearchTerm(' \t\n ')).toBe('')
    expect(normalizeSearchTerm('  hello   world  ')).toBe('hello world')
  })
})

import { describe, expect, it } from 'vitest'

import {
  buildDefaultRange,
  buildQueryKey,
  formatRangeLabel,
  resolveAppliedRange,
  toSessionIndexQuery,
  validateRange,
} from '../../../../src/features/sessions/presentation/sessionDateFilter.ts'

describe('sessionDateFilter', () => {
  it('builds the default 7-day range from the current JST date', () => {
    expect(buildDefaultRange(new Date('2026-05-03T18:15:00Z'))).toEqual({
      from: '2026-04-28',
      to: '2026-05-04',
    })
  })

  it('resolves an empty draft back to the default range', () => {
    expect(
      resolveAppliedRange(
        {
          from: '',
          to: '',
        },
        new Date('2026-05-03T02:15:00Z'),
      ),
    ).toEqual({
      from: '2026-04-27',
      to: '2026-05-03',
    })
  })

  it('treats only from > to as invalid and keeps one-sided ranges valid', () => {
    expect(
      validateRange({
        from: '2026-05-08',
        to: '2026-05-07',
      }),
    ).toEqual({
      kind: 'invalid',
      field: 'range',
      message: '開始日は終了日以前にしてください。',
    })

    expect(
      validateRange({
        from: '2026-05-08',
        to: '',
      }),
    ).toEqual({ kind: 'valid' })
    expect(
      validateRange({
        from: '',
        to: '2026-05-07',
      }),
    ).toEqual({ kind: 'valid' })
  })

  it('serializes inclusive JST boundaries for both ends', () => {
    expect(
      toSessionIndexQuery({
        from: '2026-05-01',
        to: '2026-05-07',
      }),
    ).toEqual({
      from: '2026-05-01T00:00:00+09:00',
      to: '2026-05-07T23:59:59.999999+09:00',
    })
  })

  it('builds a stable label and query key from the resolved range', () => {
    const range = {
      from: '2026-05-01',
      to: '2026-05-07',
    }

    expect(formatRangeLabel(range)).toBe('2026-05-01 〜 2026-05-07')
    expect(buildQueryKey(range)).toBe('from=2026-05-01|to=2026-05-07')
  })
})

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
  /**
   * 概要・目的: 「builds the default 7-day range from the current JST date」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「builds the default 7-day range from the current JST date」の条件・入力・操作を実行する。
   * 期待値: the default 7-day range from the current JST date が構築されること。
   */
  it('builds the default 7-day range from the current JST date', () => {
    expect(buildDefaultRange(new Date('2026-05-03T18:15:00Z'))).toEqual({
      from: '2026-04-28',
      to: '2026-05-04',
    })
  })

  /**
   * 概要・目的: 「resolves an empty draft back to the default range」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「resolves an empty draft back to the default range」の条件・入力・操作を実行する。
   * 期待値: 「resolves an empty draft back to the default range」で示す状態または振る舞いが成立すること。
   */
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

  /**
   * 概要・目的: 「treats only from > to as invalid and keeps one-sided ranges valid」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「treats only from > to as invalid and keeps one-sided ranges valid」の条件・入力・操作を実行する。
   * 期待値: only from > to が invalid and keeps one-sided ranges valid として扱われること。
   */
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

  /**
   * 概要・目的: 「serializes inclusive JST boundaries for both ends」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「serializes inclusive JST boundaries for both ends」の条件・入力・操作を実行する。
   * 期待値: 「serializes inclusive JST boundaries for both ends」で示す状態または振る舞いが成立すること。
   */
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

  /**
   * 概要・目的: 「builds a stable label and query key from the resolved range」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「builds a stable label and query key from the resolved range」の条件・入力・操作を実行する。
   * 期待値: a stable label and query key from the resolved range が構築されること。
   */
  it('builds a stable label and query key from the resolved range', () => {
    const range = {
      from: '2026-05-01',
      to: '2026-05-07',
    }

    expect(formatRangeLabel(range)).toBe('2026-05-01 〜 2026-05-07')
    expect(buildQueryKey(range)).toBe('from=2026-05-01|to=2026-05-07')
  })
})

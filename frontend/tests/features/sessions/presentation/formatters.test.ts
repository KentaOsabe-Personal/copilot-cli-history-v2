import { describe, expect, it } from 'vitest'

import {
  buildSessionMetadataItems,
  buildSessionDetailSignals,
  buildSessionSummarySignals,
  formatDegradedLabel,
  formatIssueMetadata,
  formatTimestamp,
  getDisplayableModel,
  getDisplayableWorkContext,
} from '../../../../src/features/sessions/presentation/formatters.ts'

describe('formatters', () => {
  /**
   * 概要・目的: 「formats missing timestamps with a stable placeholder」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「formats missing timestamps with a stable placeholder」の条件・入力・操作を実行する。
   * 期待値: missing timestamps with a stable placeholder が表示用に整形されること。
   */
  it('formats missing timestamps with a stable placeholder', () => {
    expect(formatTimestamp(null)).toBe('時刻不明')
  })

  /**
   * 概要・目的: 「formats ISO timestamps into a stable JST label」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「formats ISO timestamps into a stable JST label」の条件・入力・操作を実行する。
   * 期待値: ISO timestamps into a stable JST label が表示用に整形されること。
   */
  it('formats ISO timestamps into a stable JST label', () => {
    expect(formatTimestamp('2026-04-26T09:05:00Z')).toBe('2026-04-26 18:05:00 JST')
  })

  /**
   * 概要・目的: 「formats JST midnight with a zero-based hour」を通じて、formatting と表示用の値変換を検証する。
   * テストケース: 「formats JST midnight with a zero-based hour」の条件・入力・操作を実行する。
   * 期待値: JST midnight with a zero-based hour が表示用に整形されること。
   */
  it('formats JST midnight with a zero-based hour', () => {
    expect(formatTimestamp('2026-04-26T15:05:00Z')).toBe('2026-04-27 00:05:00 JST')
  })

  /**
   * 概要・目的: 「keeps invalid timestamps out of the JST success format」を通じて、DB 保存・validation・一意性制約を検証する。
   * テストケース: 「keeps invalid timestamps out of the JST success format」の条件・入力・操作を実行する。
   * 期待値: invalid timestamps out of the JST success format が維持されること。
   */
  it('keeps invalid timestamps out of the JST success format', () => {
    expect(formatTimestamp('not-a-timestamp')).toBe('not-a-timestamp')
    expect(formatTimestamp('not-a-timestamp')).not.toContain('JST')
  })

  /**
   * 概要・目的: 「returns displayable work context and model values only when real metadata exists」を通じて、fallback
   *   と優先順位の分岐を検証する。
   * テストケース: 「returns displayable work context and model values only when real metadata exists」の条件・入力・操作を実行する。
   * 期待値: displayable work context and model values only when real metadata exists を返すこと。
   */
  it('returns displayable work context and model values only when real metadata exists', () => {
    expect(
      getDisplayableWorkContext({
        cwd: null,
        git_root: null,
        repository: null,
        branch: null,
      }),
    ).toBeNull()
    expect(getDisplayableModel(null)).toBeNull()
    expect(
      getDisplayableWorkContext({
        cwd: '/workspace/example',
        git_root: '/workspace/example',
        repository: 'octo/example',
        branch: 'main',
      }),
    ).toBe('octo/example @ main')
    expect(getDisplayableModel('  gpt-5.4  ')).toBe('gpt-5.4')
  })

  /**
   * 概要・目的: 「builds metadata items without placeholder-only work context or model entries」を通じて、formatting
   *   と表示用の値変換を検証する。
   * テストケース: 「builds metadata items without placeholder-only work context or model entries」の条件・入力・操作を実行する。
   * 期待値: metadata items without placeholder-only work context or model entries が構築されること。
   */
  it('builds metadata items without placeholder-only work context or model entries', () => {
    expect(
      buildSessionMetadataItems({
        createdAt: null,
        updatedAt: null,
        workContext: {
          cwd: null,
          git_root: null,
          repository: null,
          branch: null,
        },
        selectedModel: null,
      }),
    ).toEqual([
      {
        label: '更新日時',
        value: '時刻不明',
      },
    ])
  })

  /**
   * 概要・目的: 「falls back to created_at when updated_at is unavailable」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「falls back to created_at when updated_at is unavailable」の条件・入力・操作を実行する。
   * 期待値: created_at when updated_at is unavailable に fallback すること。
   */
  it('falls back to created_at when updated_at is unavailable', () => {
    expect(
      buildSessionMetadataItems({
        surface: 'summary',
        createdAt: '2026-04-26T09:00:00Z',
        updatedAt: null,
        workContext: {
          cwd: null,
          git_root: null,
          repository: null,
          branch: null,
        },
        selectedModel: null,
      }),
    ).toEqual([
      {
        label: '表示日時',
        value: '2026-04-26 18:00:00 JST',
      },
    ])
  })

  /**
   * 概要・目的: 「keeps detail metadata honest when only created_at is available」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「keeps detail metadata honest when only created_at is available」の条件・入力・操作を実行する。
   * 期待値: detail metadata honest when only created_at is available が維持されること。
   */
  it('keeps detail metadata honest when only created_at is available', () => {
    expect(
      buildSessionMetadataItems({
        surface: 'detail',
        createdAt: '2026-04-26T09:00:00Z',
        updatedAt: null,
        workContext: {
          cwd: null,
          git_root: null,
          repository: null,
          branch: null,
        },
        selectedModel: null,
      }),
    ).toEqual([
      {
        label: '作成日時',
        value: '2026-04-26 18:00:00 JST',
      },
    ])
  })

  /**
   * 概要・目的: 「formats degraded and issue metadata into readable labels」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「formats degraded and issue metadata into readable labels」の条件・入力・操作を実行する。
   * 期待値: degraded and issue metadata into readable labels が表示用に整形されること。
   */
  it('formats degraded and issue metadata into readable labels', () => {
    expect(formatDegradedLabel(true)).toBe('一部欠損あり')
    expect(formatDegradedLabel(false)).toBe('正常')
    expect(
      formatIssueMetadata({
        severity: 'warning',
        scope: 'event',
        event_sequence: 8,
      }),
    ).toEqual({
      severityLabel: '警告',
      scopeLabel: 'イベント',
      locationLabel: 'イベント #8',
    })
  })

  /**
   * 概要・目的: 「builds only exceptional session signals for summary and detail
   *   surfaces」を通じて、正規化・projection・presenter の変換契約を検証する。
   * テストケース: 「builds only exceptional session signals for summary and detail surfaces」の条件・入力・操作を実行する。
   * 期待値: only exceptional session signals for summary and detail surfaces が構築されること。
   */
  it('builds only exceptional session signals for summary and detail surfaces', () => {
    expect(
      buildSessionSummarySignals({
        hasConversation: true,
        degraded: false,
        sourceState: 'complete',
      }),
    ).toEqual([])
    expect(
      buildSessionSummarySignals({
        hasConversation: false,
        degraded: false,
        sourceState: 'complete',
      }),
    ).toEqual([{ label: 'metadata-only', tone: 'neutral' }])
    expect(
      buildSessionSummarySignals({
        hasConversation: false,
        degraded: false,
        sourceState: 'workspace_only',
      }),
    ).toEqual([{ label: 'workspace-only', tone: 'warning' }])
    expect(
      buildSessionSummarySignals({
        hasConversation: true,
        degraded: false,
        sourceState: 'workspace_only',
      }),
    ).toEqual([{ label: 'workspace-only', tone: 'warning' }])
    expect(
      buildSessionSummarySignals({
        hasConversation: true,
        degraded: true,
        sourceState: 'degraded',
      }),
    ).toEqual([])
    expect(
      buildSessionDetailSignals({
        degraded: true,
        sourceState: 'degraded',
      }),
    ).toEqual([{ label: '一部欠損あり', tone: 'warning' }])
  })
})

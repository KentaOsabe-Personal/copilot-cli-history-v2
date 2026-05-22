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
   * 概要・目的: summary metadata で実行ディレクトリを repository / branch と独立して表示できることを検証する。
   * テストケース: cwd、repository、branch が同時に存在する summary metadata を構築する。
   * 期待値: 作業コンテキストと実行ディレクトリの両方が metadata item として返ること。
   */
  it('builds summary metadata with execution directory alongside repository and branch', () => {
    expect(
      buildSessionMetadataItems({
        surface: 'summary',
        createdAt: '2026-04-26T09:00:00Z',
        updatedAt: '2026-04-26T09:05:00Z',
        workContext: {
          cwd: '  /workspace/copilot-cli-history/frontend  ',
          git_root: '/workspace/copilot-cli-history',
          repository: 'octo/copilot-cli-history',
          branch: 'main',
        },
        selectedModel: null,
      }),
    ).toEqual([
      {
        label: '表示日時',
        value: '2026-04-26 18:05:00 JST',
      },
      {
        label: '作業コンテキスト',
        value: 'octo/copilot-cli-history @ main',
      },
      {
        label: '実行ディレクトリ',
        value: '/workspace/copilot-cli-history/frontend',
      },
    ])
  })

  /**
   * 概要・目的: summary metadata で cwd 欠損時に空項目や placeholder を表示しないことを検証する。
   * テストケース: cwd が null または空白で、repository / branch が存在する summary metadata を構築する。
   * 期待値: 実行ディレクトリ item は返らず、作業コンテキストだけが維持されること。
   */
  it('omits execution directory metadata when cwd is missing or blank', () => {
    expect(
      buildSessionMetadataItems({
        surface: 'summary',
        createdAt: '2026-04-26T09:00:00Z',
        updatedAt: null,
        workContext: {
          cwd: '   ',
          git_root: '/workspace/copilot-cli-history',
          repository: 'octo/copilot-cli-history',
          branch: 'main',
        },
        selectedModel: null,
      }),
    ).toEqual([
      {
        label: '表示日時',
        value: '2026-04-26 18:00:00 JST',
      },
      {
        label: '作業コンテキスト',
        value: 'octo/copilot-cli-history @ main',
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
   * 概要・目的: summary と detail で表示対象に残す session signal の境界を検証する。
   * テストケース: 会話有無、workspace-only、degraded の signal を summary と detail 向けに構築する。
   * 期待値: summary は既存の例外 signal を維持し、detail の degraded signal は表示対象から外れること。
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
        sourceState: 'degraded',
      }),
    ).toEqual([])
  })
})

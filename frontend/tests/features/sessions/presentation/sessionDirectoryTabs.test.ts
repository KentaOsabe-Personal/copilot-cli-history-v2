import { describe, expect, it } from 'vitest'

import type { SessionSummary } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import {
  buildSessionDirectoryTabs,
  coerceDirectoryTabKey,
  getSessionsForDirectoryTab,
  type SessionDirectoryTabKey,
} from '../../../../src/features/sessions/presentation/sessionDirectoryTabs.ts'

function buildSessionSummary(id: string, cwd: string | null): SessionSummary {
  return {
    id,
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: {
      cwd,
      git_root: null,
      repository: null,
      branch: null,
    },
    selected_model: 'gpt-5.4',
    source_state: 'complete',
    event_count: 5,
    message_snapshot_count: 3,
    conversation_summary: {
      has_conversation: true,
      message_count: 2,
      preview: '履歴を確認したい',
      activity_count: 3,
    },
    degraded: false,
    issues: [],
  }
}

describe('sessionDirectoryTabs', () => {
  /**
   * 概要・目的: 成功状態の取得済みセッション集合だけから、全件タブと作業ディレクトリ別タブを再現できる契約を検証する。
   * テストケース: 異なる cwd を持つ 3 件のセッションでタブモデルを構築する。
   * 期待値: `すべて` が先頭にあり、各 cwd の basename と件数が初出順で表示されること。
   */
  it('builds the all tab and directory tabs in first-seen order', () => {
    const sessions = [
      buildSessionSummary('session-a', '/workspace/project-a'),
      buildSessionSummary('session-b', '/workspace/project-b'),
      buildSessionSummary('session-c', '/workspace/project-a'),
    ]

    expect(buildSessionDirectoryTabs(sessions).tabs).toEqual([
      {
        key: 'all',
        kind: 'all',
        label: 'すべて',
        contextLabel: null,
        fullPath: null,
        count: 3,
      },
      {
        key: 'cwd:/workspace/project-a',
        kind: 'directory',
        label: 'project-a',
        contextLabel: null,
        fullPath: '/workspace/project-a',
        count: 2,
      },
      {
        key: 'cwd:/workspace/project-b',
        kind: 'directory',
        label: 'project-b',
        contextLabel: null,
        fullPath: '/workspace/project-b',
        count: 1,
      },
    ])
  })

  /**
   * 概要・目的: cwd の前後空白だけが異なるセッションを同じ作業ディレクトリとして扱う契約を検証する。
   * テストケース: trim 前後で同じ cwd になる 2 件と別 cwd 1 件でタブを構築する。
   * 期待値: trim 後の cwd が 1 つのタブに集約され、件数と fullPath が正規化後の値になること。
   */
  it('groups sessions by trimmed cwd values', () => {
    const sessions = [
      buildSessionSummary('session-a', '  /workspace/project-a  '),
      buildSessionSummary('session-b', '/workspace/project-a'),
      buildSessionSummary('session-c', '/workspace/project-b'),
    ]

    const tabs = buildSessionDirectoryTabs(sessions).tabs

    expect(tabs[1]).toMatchObject({
      key: 'cwd:/workspace/project-a',
      fullPath: '/workspace/project-a',
      count: 2,
    })
  })

  /**
   * 概要・目的: null や空白 cwd のセッションを落とさず、未設定タブへまとめる契約を検証する。
   * テストケース: null cwd、空白 cwd、通常 cwd を含むセッション集合でタブを構築する。
   * 期待値: `ディレクトリ未設定` タブが最後に追加され、未設定セッション 2 件を数えること。
   */
  it('groups null and blank cwd values into the unset tab at the end', () => {
    const sessions = [
      buildSessionSummary('session-a', null),
      buildSessionSummary('session-b', '/workspace/project-a'),
      buildSessionSummary('session-c', '   '),
    ]

    expect(buildSessionDirectoryTabs(sessions).tabs).toEqual([
      expect.objectContaining({ key: 'all', count: 3 }),
      expect.objectContaining({ key: 'cwd:/workspace/project-a', count: 1 }),
      {
        key: 'unset',
        kind: 'unset',
        label: 'ディレクトリ未設定',
        contextLabel: null,
        fullPath: null,
        count: 2,
      },
    ])
  })

  /**
   * 概要・目的: 同じ basename の作業ディレクトリを、最短一意の親パス文脈で区別する契約を検証する。
   * テストケース: basename が `app` で重複し、1 階層の親だけでは一意にならない cwd を含める。
   * 期待値: 重複 group 内で `contextLabel/label` が一意になる最短 suffix が付与されること。
   */
  it('adds the shortest unique parent context for duplicate basenames', () => {
    const sessions = [
      buildSessionSummary('session-a', '/workspace/team/frontend/app'),
      buildSessionSummary('session-b', '/workspace/admin/frontend/app'),
      buildSessionSummary('session-c', '/workspace/mobile/app'),
    ]

    const tabs = buildSessionDirectoryTabs(sessions).tabs

    expect(tabs.slice(1)).toEqual([
      expect.objectContaining({
        key: 'cwd:/workspace/team/frontend/app',
        label: 'app',
        contextLabel: 'team/frontend',
      }),
      expect.objectContaining({
        key: 'cwd:/workspace/admin/frontend/app',
        label: 'app',
        contextLabel: 'admin/frontend',
      }),
      expect.objectContaining({
        key: 'cwd:/workspace/mobile/app',
        label: 'app',
        contextLabel: 'mobile',
      }),
    ])
  })

  /**
   * 概要・目的: タブ選択時に表示対象セッションだけを既存の相対順で返す契約を検証する。
   * テストケース: 同じ cwd のセッションが全体の 1 件目と 3 件目にある状態で、その cwd のタブを選択する。
   * 期待値: 対応する 2 件だけが元の相対順のまま返ること。
   */
  it('filters sessions for a directory tab while preserving relative order', () => {
    const sessions = [
      buildSessionSummary('session-a', '/workspace/project-a'),
      buildSessionSummary('session-b', '/workspace/project-b'),
      buildSessionSummary('session-c', ' /workspace/project-a '),
    ]

    const filtered = getSessionsForDirectoryTab(sessions, 'cwd:/workspace/project-a')

    expect(filtered.map((session) => session.id)).toEqual(['session-a', 'session-c'])
  })

  /**
   * 概要・目的: 未設定タブ選択時に null と空白 cwd のセッションだけを既存順で返す契約を検証する。
   * テストケース: null、通常 cwd、空白 cwd の順に並ぶセッションで未設定タブを選択する。
   * 期待値: null と空白 cwd の 2 件だけが元の相対順で返ること。
   */
  it('filters sessions for the unset tab while preserving relative order', () => {
    const sessions = [
      buildSessionSummary('session-a', null),
      buildSessionSummary('session-b', '/workspace/project-b'),
      buildSessionSummary('session-c', '   '),
    ]

    const filtered = getSessionsForDirectoryTab(sessions, 'unset')

    expect(filtered.map((session) => session.id)).toEqual(['session-a', 'session-c'])
  })

  /**
   * 概要・目的: 新しい成功結果に存在しない選択タブを `すべて` に補正する契約を検証する。
   * テストケース: 現在のタブ集合に含まれない cwd key を補正する。
   * 期待値: `all` が返り、存在する cwd key と `unset` はそのまま返ること。
   */
  it('coerces missing selected tab keys to all', () => {
    const tabs = buildSessionDirectoryTabs([
      buildSessionSummary('session-a', '/workspace/project-a'),
      buildSessionSummary('session-b', null),
    ]).tabs

    expect(coerceDirectoryTabKey('cwd:/workspace/missing', tabs)).toBe('all')
    expect(coerceDirectoryTabKey('cwd:/workspace/project-a', tabs)).toBe('cwd:/workspace/project-a')
    expect(coerceDirectoryTabKey('unset', tabs)).toBe('unset')
  })

  /**
   * 概要・目的: `すべて` タブ選択時に取得済みセッション集合をそのまま返す契約を検証する。
   * テストケース: 複数 cwd と未設定 cwd を含むセッション集合で `すべて` を選択する。
   * 期待値: 全セッションが入力順のまま返ること。
   */
  it('returns all sessions for the all tab', () => {
    const sessions = [
      buildSessionSummary('session-a', '/workspace/project-a'),
      buildSessionSummary('session-b', null),
      buildSessionSummary('session-c', '/workspace/project-c'),
    ]

    const filtered = getSessionsForDirectoryTab(sessions, 'all')

    expect(filtered).toBe(sessions)
  })

  /**
   * 概要・目的: 型外から渡された不正な key でも、補正関数が安全に `すべて` へ戻す契約を検証する。
   * テストケース: `SessionDirectoryTabKey` として扱われた未知文字列を補正する。
   * 期待値: 現在のタブ集合に存在しないため `all` が返ること。
   */
  it('treats unknown selected tab keys as missing', () => {
    const tabs = buildSessionDirectoryTabs([buildSessionSummary('session-a', '/workspace/project-a')]).tabs
    const unknownKey = 'unknown' as SessionDirectoryTabKey

    expect(coerceDirectoryTabKey(unknownKey, tabs)).toBe('all')
  })
})

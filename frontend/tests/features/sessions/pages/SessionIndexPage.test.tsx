import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SessionSummary } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import type { HistorySyncState, UseHistorySyncResult } from '../../../../src/features/sessions/hooks/useHistorySync.ts'
import { useHistorySync } from '../../../../src/features/sessions/hooks/useHistorySync.ts'
import type { SessionIndexState, UseSessionIndexResult } from '../../../../src/features/sessions/hooks/useSessionIndex.ts'
import { useSessionIndex } from '../../../../src/features/sessions/hooks/useSessionIndex.ts'
import type { SessionDateRangeDraft } from '../../../../src/features/sessions/presentation/sessionDateFilter.ts'
import SessionIndexPage from '../../../../src/features/sessions/pages/SessionIndexPage.tsx'

vi.mock('../../../../src/features/sessions/hooks/useHistorySync.ts', () => ({
  useHistorySync: vi.fn(),
}))

vi.mock('../../../../src/features/sessions/hooks/useSessionIndex.ts', () => ({
  useSessionIndex: vi.fn(),
}))

const mockedUseHistorySync = vi.mocked(useHistorySync)
const mockedUseSessionIndex = vi.mocked(useSessionIndex)
const DEFAULT_APPLIED_RANGE: SessionDateRangeDraft = {
  from: '2026-04-28',
  to: '2026-05-04',
}

function buildUseSessionIndexResult(
  state: SessionIndexState,
  appliedRange: SessionDateRangeDraft = DEFAULT_APPLIED_RANGE,
  overrides: Partial<
    Pick<UseSessionIndexResult, 'isRefreshing' | 'applyRange' | 'reloadSessions' | 'applySearch' | 'clearSearch' | 'appliedSearchTerm'>
  > = {},
): UseSessionIndexResult {
  const reloadOutcome =
    state.status === 'loading'
      ? ({ status: 'empty' } as const)
      : state

  const reloadSessions = overrides.reloadSessions ?? (async () => reloadOutcome)

  return {
    state,
    appliedRange,
    appliedSearchTerm: overrides.appliedSearchTerm ?? '',
    isRefreshing: overrides.isRefreshing ?? false,
    applyRange: overrides.applyRange ?? vi.fn(async () => reloadOutcome),
    applySearch: overrides.applySearch ?? vi.fn(async () => reloadOutcome),
    clearSearch: overrides.clearSearch ?? vi.fn(async () => reloadOutcome),
    reloadSessions,
  }
}

function buildUseHistorySyncResult(
  state: HistorySyncState = { status: 'idle' },
  overrides: Partial<Pick<UseHistorySyncResult, 'isSyncing' | 'startSync'>> = {},
): UseHistorySyncResult {
  return {
    state,
    isSyncing: state.status === 'syncing',
    startSync: vi.fn(async () => undefined),
    ...overrides,
  }
}

function buildSessionSummary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: 'session-123',
    source_format: 'current',
    created_at: '2026-04-26T09:00:00Z',
    updated_at: '2026-04-26T09:05:00Z',
    work_context: {
      cwd: '/workspace/session-123',
      git_root: '/workspace/session-123',
      repository: 'octo/example',
      branch: 'main',
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
    ...overrides,
  }
}

describe('SessionIndexPage', () => {
  beforeEach(() => {
    mockedUseHistorySync.mockReset()
    mockedUseSessionIndex.mockReset()
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult())
  })

  /**
   * 概要・目的: 「renders a loading panel while the session index is being fetched」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「renders a loading panel while the session index is being fetched」の条件・入力・操作を実行する。
   * 期待値: a loading panel while the session index is being fetched が画面に表示されること。
   */
  it('renders a loading panel while the session index is being fetched', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'loading' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'セッション一覧' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を読み込んでいます' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps the attempted applied range visible inside the loading panel context」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「keeps the attempted applied range visible inside the loading panel context」の条件・入力・操作を実行する。
   * 期待値: the attempted applied range visible inside the loading panel context が維持されること。
   */
  it('keeps the attempted applied range visible inside the loading panel context', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'loading' },
        {
          from: '2026-05-01',
          to: '2026-05-07',
        },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(
      screen.getByText('現在の表示範囲: 2026-05-01 〜 2026-05-07 のセッションを確認しています。'),
    ).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders the date filter form with the hook-applied range as the current confirmed
   *   range」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「renders the date filter form with the hook-applied range as the current confirmed
   *   range」の条件・入力・操作を実行する。
   * 期待値: the date filter form with the hook-applied range as the current confirmed range が画面に表示されること。
   */
  it('renders the date filter form with the hook-applied range as the current confirmed range', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '日付範囲で絞り込む' })).toBeInTheDocument()
    expect(screen.getByLabelText('開始日')).toHaveValue('2026-04-28')
    expect(screen.getByLabelText('終了日')).toHaveValue('2026-05-04')
    expect(screen.getAllByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toHaveLength(2)
  })

  /**
   * 概要・目的: 「renders the search form and applies a search without changing the date range」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「renders the search form and applies a search without changing the date range」の条件・入力・操作を実行する。
   * 期待値: the search form が表示され、a search without changing the date range が適用されること。
   */
  it('renders the search form and applies a search without changing the date range', async () => {
    const user = userEvent.setup()
    const applySearch = vi.fn(async () => ({ status: 'empty' } as const))

    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'success', sessions: [buildSessionSummary()], meta: { count: 1, partial_results: false } },
        DEFAULT_APPLIED_RANGE,
        { applySearch },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '検索語で絞り込む' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('検索語'), 'apply patch')
    await user.click(screen.getByRole('button', { name: '検索する' }))

    expect(applySearch).toHaveBeenCalledWith('apply patch')
    expect(screen.getByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「submits the page-owned draft range through applyRange while keeping the confirmed label on the
   *   hook state」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「submits the page-owned draft range through applyRange while keeping the confirmed label on the
   *   hook state」の条件・入力・操作を実行する。
   * 期待値: 「submits the page-owned draft range through applyRange while keeping the confirmed label on the hook
   *   state」で示す状態または振る舞いが成立すること。
   */
  it('submits the page-owned draft range through applyRange while keeping the confirmed label on the hook state', async () => {
    const user = userEvent.setup()
    const applyRange = vi.fn(async () => ({ status: 'empty' } as const))

    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'success', sessions: [buildSessionSummary()], meta: { count: 1, partial_results: false } },
        DEFAULT_APPLIED_RANGE,
        { applyRange },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    await user.clear(screen.getByLabelText('開始日'))
    await user.type(screen.getByLabelText('開始日'), '2026-05-01')
    await user.clear(screen.getByLabelText('終了日'))
    await user.type(screen.getByLabelText('終了日'), '2026-05-07')
    await user.click(screen.getByRole('button', { name: '適用する' }))

    expect(applyRange).toHaveBeenCalledWith({
      from: '2026-05-01',
      to: '2026-05-07',
    })
    expect(screen.getByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「lets the page submit an empty draft so the hook can reset back to the default 7-day
   *   range」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「lets the page submit an empty draft so the hook can reset back to the default 7-day
   *   range」の条件・入力・操作を実行する。
   * 期待値: 「lets the page submit an empty draft so the hook can reset back to the default 7-day
   *   range」で示す状態または振る舞いが成立すること。
   */
  it('lets the page submit an empty draft so the hook can reset back to the default 7-day range', async () => {
    const user = userEvent.setup()
    const applyRange = vi.fn(async () => ({ status: 'empty' } as const))

    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'empty' },
        {
          from: '2026-05-01',
          to: '2026-05-07',
        },
        { applyRange },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    await user.clear(screen.getByLabelText('開始日'))
    await user.clear(screen.getByLabelText('終了日'))
    await user.click(screen.getByRole('button', { name: '適用する' }))

    expect(applyRange).toHaveBeenCalledWith({
      from: '',
      to: '',
    })
  })

  /**
   * 概要・目的: 「renders an empty-state sync action when the backend returns no sessions」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders an empty-state sync action when the backend returns no sessions」の条件・入力・操作を実行する。
   * 期待値: an empty-state sync action when the backend returns no sessions が画面に表示されること。
   */
  it('renders an empty-state sync action when the backend returns no sessions', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'この日付範囲に一致するセッションはありません' })).toBeInTheDocument()
    expect(screen.getAllByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toHaveLength(2)
    expect(screen.getByRole('button', { name: '履歴を取り込む' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders search loading and search empty states with the applied criteria」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「renders search loading and search empty states with the applied criteria」の条件・入力・操作を実行する。
   * 期待値: search loading が表示され、search empty states with the applied criteriaこと。
   */
  it('renders search loading and search empty states with the applied criteria', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'loading' },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'apply patch' },
      ),
    )

    const { rerender } = render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '検索条件を含むセッション一覧を読み込んでいます' })).toBeInTheDocument()
    expect(
      screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch のセッションを確認しています。'),
    ).toBeInTheDocument()

    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'empty' },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'apply patch' },
      ),
    )

    rerender(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '検索条件に一致するセッションはありません' })).toBeInTheDocument()
    expect(screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders search result context above the list when a search is applied」を通じて、検索・日付条件と query
   *   組み立てを検証する。
   * テストケース: 「renders search result context above the list when a search is applied」の条件・入力・操作を実行する。
   * 期待値: search result context above the list when a search is applied が画面に表示されること。
   */
  it('renders search result context above the list when a search is applied', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        {
          status: 'success',
          sessions: [buildSessionSummary()],
          meta: { count: 1, partial_results: false },
        },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'apply patch' },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(
      screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch の検索結果を表示しています。'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「clears an applied search from the empty state while preserving the date criteria」を通じて、検索・日付条件と
   *   query 組み立てを検証する。
   * テストケース: 「clears an applied search from the empty state while preserving the date criteria」の条件・入力・操作を実行する。
   * 期待値: 「clears an applied search from the empty state while preserving the date
   *   criteria」で示す状態または振る舞いが成立すること。
   */
  it('clears an applied search from the empty state while preserving the date criteria', async () => {
    const user = userEvent.setup()
    const clearSearch = vi.fn(async () => ({ status: 'empty' } as const))

    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'empty' },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'apply patch', clearSearch },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    await user.click(screen.getAllByRole('button', { name: '検索を解除' })[1])

    expect(clearSearch).toHaveBeenCalledTimes(1)
    expect(screen.getByText('現在の検索条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps a user-selected empty range visible in the empty state copy」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「keeps a user-selected empty range visible in the empty state copy」の条件・入力・操作を実行する。
   * 期待値: a user-selected empty range visible in the empty state copy が維持されること。
   */
  it('keeps a user-selected empty range visible in the empty state copy', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        { status: 'empty' },
        {
          from: '2026-05-01',
          to: '2026-05-07',
        },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getAllByText('現在の表示範囲: 2026-05-01 〜 2026-05-07')).toHaveLength(2)
  })

  /**
   * 概要・目的: 「renders ordered session cards without placeholder-only work context or model
   *   metadata」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「renders ordered session cards without placeholder-only work context or model
   *   metadata」の条件・入力・操作を実行する。
   * 期待値: ordered session cards without placeholder-only work context or model metadata が画面に表示されること。
   */
  it('renders ordered session cards without placeholder-only work context or model metadata', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'session-b',
          updated_at: '2026-04-26T10:05:00Z',
          degraded: true,
        }),
        buildSessionSummary({
          id: 'session-a',
          updated_at: null,
          work_context: {
            cwd: null,
            git_root: null,
            repository: null,
            branch: null,
          },
          selected_model: null,
        }),
      ],
      meta: {
        count: 2,
        partial_results: true,
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /を開く$/ }).map((node) => node.getAttribute('href'))).toEqual([
      '/sessions/session-b',
      '/sessions/session-a',
    ])
    expect(screen.queryByText('一部欠損あり')).not.toBeInTheDocument()
    expect(screen.getByText('2026-04-26 18:00:00 JST')).toBeInTheDocument()
    expect(screen.queryByText('作業コンテキスト不明')).not.toBeInTheDocument()
    expect(screen.queryByText('モデル不明')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-b を開く' })).toHaveAttribute(
      'href',
      '/sessions/session-b',
    )
  })

  /**
   * 概要・目的: 「keeps normal sessions free of always-on status badges while surfacing exceptional
   *   states」を通じて、HTTP レスポンスとエラー契約を検証する。
   * テストケース: 「keeps normal sessions free of always-on status badges while surfacing exceptional
   *   states」の条件・入力・操作を実行する。
   * 期待値: normal sessions free of always-on status badges while surfacing exceptional states が維持されること。
   */
  it('keeps normal sessions free of always-on status badges while surfacing exceptional states', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'conversation-session',
          updated_at: '2026-04-26T10:05:00Z',
          conversation_summary: {
            has_conversation: true,
            message_count: 4,
            preview: '次の実装方針を相談したい',
            activity_count: 7,
          },
        }),
        buildSessionSummary({
          id: 'metadata-only-session',
          conversation_summary: {
            has_conversation: false,
            message_count: 0,
            preview: null,
            activity_count: 0,
          },
        }),
        buildSessionSummary({
          id: 'workspace-only-session',
          source_state: 'workspace_only',
          conversation_summary: {
            has_conversation: false,
            message_count: 0,
            preview: null,
            activity_count: 0,
          },
        }),
      ],
      meta: {
        count: 3,
        partial_results: false,
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByText('4 件の会話')).toBeInTheDocument()
    expect(screen.getByText('次の実装方針を相談したい')).toBeInTheDocument()
    expect(screen.getByText('2026-04-26 19:05:00 JST')).toBeInTheDocument()
    expect(screen.queryByText('会話あり')).not.toBeInTheDocument()
    expect(screen.queryByText('正常')).not.toBeInTheDocument()
    expect(screen.queryByText('complete')).not.toBeInTheDocument()
    expect(screen.queryByText('7 件の内部 activity')).not.toBeInTheDocument()
    expect(screen.getByText('metadata-only')).toBeInTheDocument()
    expect(screen.getByText('workspace-only')).toBeInTheDocument()
    expect(screen.getAllByText('表示できる会話本文はありません')).toHaveLength(2)
  })

  /**
   * 概要・目的: 「renders an error panel without success cards when the fetch fails」を通じて、hook の状態遷移と非同期制御を検証する。
   * テストケース: 「renders an error panel without success cards when the fetch fails」の条件・入力・操作を実行する。
   * 期待値: an error panel without success cards when the fetch fails が画面に表示されること。
   */
  it('renders an error panel without success cards when the fetch fails', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 503,
        code: 'root_missing',
        message: 'history root does not exist',
        details: {
          path: '/tmp/.copilot',
        },
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を最新化' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を表示できません' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'session-123 を開く' })).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders search-condition client errors separately from generic list
   *   failures」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders search-condition client errors separately from generic list failures」の条件・入力・操作を実行する。
   * 期待値: search-condition client errors separately from generic list failures が画面に表示されること。
   */
  it('renders search-condition client errors separately from generic list failures', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        {
          status: 'error',
          error: {
            kind: 'backend',
            httpStatus: 400,
            code: 'invalid_session_list_query',
            message: 'session list query is invalid',
            details: {
              field: 'search',
              reason: 'control_character',
            },
          },
        },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'bad' },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '検索条件を確認してください' })).toBeInTheDocument()
    expect(screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: bad を見直して再度検索してください。')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('検索条件を確認してください。')
  })

  /**
   * 概要・目的: 「keeps generic search fetch failures aligned to the applied search
   *   criteria」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps generic search fetch failures aligned to the applied search criteria」の条件・入力・操作を実行する。
   * 期待値: generic search fetch failures aligned to the applied search criteria が維持されること。
   */
  it('keeps generic search fetch failures aligned to the applied search criteria', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        {
          status: 'error',
          error: {
            kind: 'backend',
            httpStatus: 503,
            code: 'root_missing',
            message: 'history root does not exist',
            details: {
              path: '/tmp/.copilot',
            },
          },
        },
        DEFAULT_APPLIED_RANGE,
        { appliedSearchTerm: 'apply patch' },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'セッション一覧を表示できません' })).toBeInTheDocument()
    expect(
      screen.getByText('現在の表示条件: 2026-04-28 〜 2026-05-04 / 検索: apply patch の一覧取得に失敗しました。時間をおいて再度開くか、条件を見直してください。'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'session-123 を開く' })).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps a new-range error aligned to the attempted applied range instead of stale success
   *   content」を通じて、検索・日付条件と query 組み立てを検証する。
   * テストケース: 「keeps a new-range error aligned to the attempted applied range instead of stale success
   *   content」の条件・入力・操作を実行する。
   * 期待値: a new-range error aligned to the attempted applied range instead of stale success content が維持されること。
   */
  it('keeps a new-range error aligned to the attempted applied range instead of stale success content', () => {
    mockedUseSessionIndex.mockReturnValue(
      buildUseSessionIndexResult(
        {
          status: 'error',
          error: {
            kind: 'backend',
            httpStatus: 503,
            code: 'root_missing',
            message: 'history root does not exist',
            details: {
              path: '/tmp/.copilot',
            },
          },
        },
        {
          from: '2026-05-01',
          to: '2026-05-07',
        },
      ),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('現在の表示範囲: 2026-05-01 〜 2026-05-07')).toBeInTheDocument()
    expect(
      screen.getByText('現在の表示範囲: 2026-05-01 〜 2026-05-07 の一覧取得に失敗しました。時間をおいて再度開いてください。'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'session-123 を開く' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'この日付範囲に一致するセッションはありません' })).not.toBeInTheDocument()
  })

  /**
   * 概要・目的: 「navigates to the detail route when a session card is selected」を通じて、正規化・projection・presenter
   *   の変換契約を検証する。
   * テストケース: 「navigates to the detail route when a session card is selected」の条件・入力・操作を実行する。
   * 期待値: 「navigates to the detail route when a session card is selected」で示す状態または振る舞いが成立すること。
   */
  it('navigates to the detail route when a session card is selected', async () => {
    const user = userEvent.setup()

    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [
        buildSessionSummary({
          id: 'session-123',
        }),
      ],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<SessionIndexPage />} />
          <Route path="/sessions/:sessionId" element={<p>detail route</p>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: 'session-123 を開く' }))

    expect(screen.getByText('detail route')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「starts the same sync request from the top control and the empty-state
   *   action」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「starts the same sync request from the top control and the empty-state action」の条件・入力・操作を実行する。
   * 期待値: the top control and the empty-state action から the same sync request が開始されること。
   */
  it('starts the same sync request from the top control and the empty-state action', async () => {
    const user = userEvent.setup()
    const startSync = vi.fn(async () => undefined)

    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(
      buildUseHistorySyncResult({ status: 'idle' }, { startSync }),
    )

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: '履歴を最新化' }))
    await user.click(screen.getByRole('button', { name: '履歴を取り込む' }))

    expect(startSync).toHaveBeenCalledTimes(2)
  })

  /**
   * 概要・目的: 「disables both sync actions while syncing from an empty page」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「disables both sync actions while syncing from an empty page」の条件・入力・操作を実行する。
   * 期待値: 「disables both sync actions while syncing from an empty page」で示す状態または振る舞いが成立すること。
   */
  it('disables both sync actions while syncing from an empty page', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({ status: 'syncing' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '履歴を取り込み中...' })).toBeDisabled()
  })

  /**
   * 概要・目的: 「renders synced sessions with a completion banner and the existing list」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders synced sessions with a completion banner and the existing list」の条件・入力・操作を実行する。
   * 期待値: synced sessions with a completion banner が表示され、the existing listこと。
   */
  it('renders synced sessions with a completion banner and the existing list', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'synced_with_sessions',
      result: {
        sync_run: {
          id: 42,
          status: 'completed',
          started_at: '2026-04-30T09:00:00Z',
          finished_at: '2026-04-30T09:00:03Z',
        },
        counts: {
          processed_count: 5,
          inserted_count: 2,
          updated_count: 1,
          saved_count: 3,
          skipped_count: 2,
          failed_count: 0,
          degraded_count: 0,
        },
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴を最新化しました' })).toBeInTheDocument()
    expect(screen.getByText('3 件を保存しました。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps the same date-filter experience after sync when current and legacy sessions share the
   *   result list」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps the same date-filter experience after sync when current and legacy sessions share the
   *   result list」の条件・入力・操作を実行する。
   * 期待値: the same date-filter experience after sync when current が維持され、legacy sessions share the result
   *   listこと。
   */
  it('keeps the same date-filter experience after sync when current and legacy sessions share the result list', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult(
      {
        status: 'success',
        sessions: [
          buildSessionSummary({
            id: 'current-session',
            source_format: 'current',
          }),
          buildSessionSummary({
            id: 'legacy-session',
            source_format: 'legacy',
          }),
        ],
        meta: {
          count: 2,
          partial_results: false,
        },
      },
      {
        from: '2026-05-01',
        to: '',
      },
    ))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'synced_with_sessions',
      result: {
        sync_run: {
          id: 42,
          status: 'completed',
          started_at: '2026-04-30T09:00:00Z',
          finished_at: '2026-04-30T09:00:03Z',
        },
        counts: {
          processed_count: 5,
          inserted_count: 2,
          updated_count: 1,
          saved_count: 3,
          skipped_count: 2,
          failed_count: 0,
          degraded_count: 0,
        },
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('現在の表示範囲: 2026-05-01 以降')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '履歴を最新化しました' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'current-session を開く' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'legacy-session を開く' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders a synced-empty banner and keeps the empty state distinct from
   *   failure」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a synced-empty banner and keeps the empty state distinct from failure」の条件・入力・操作を実行する。
   * 期待値: a synced-empty banner が表示され、the empty state distinct from failure が維持されること。
   */
  it('renders a synced-empty banner and keeps the empty state distinct from failure', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({ status: 'empty' }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'synced_empty',
      result: {
        sync_run: {
          id: 42,
          status: 'completed',
          started_at: '2026-04-30T09:00:00Z',
          finished_at: '2026-04-30T09:00:03Z',
        },
        counts: {
          processed_count: 1,
          inserted_count: 0,
          updated_count: 0,
          saved_count: 0,
          skipped_count: 1,
          failed_count: 0,
          degraded_count: 0,
        },
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴の同期は完了しました' })).toBeInTheDocument()
    expect(screen.getByText('取り込みは完了しましたが、表示できるセッションはまだありません。')).toBeInTheDocument()
    expect(screen.getAllByText('現在の表示範囲: 2026-04-28 〜 2026-05-04')).toHaveLength(2)
    expect(screen.getByRole('button', { name: '履歴を取り込む' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders the %s banner without hiding the current list」を通じて、reader と fixture の読取・劣化時の扱いを検証する。
   * テストケース: 「renders the %s banner without hiding the current list」の条件・入力・操作を実行する。
   * 期待値: the %s banner without hiding the current list が画面に表示されること。
   */
  it.each([
    {
      name: 'refresh error',
      syncState: {
        status: 'refresh_error',
        result: {
          sync_run: {
            id: 42,
            status: 'completed',
            started_at: '2026-04-30T09:00:00Z',
            finished_at: '2026-04-30T09:00:03Z',
          },
          counts: {
            processed_count: 5,
            inserted_count: 2,
            updated_count: 1,
            saved_count: 3,
            skipped_count: 2,
            failed_count: 0,
            degraded_count: 0,
          },
        },
        error: {
          kind: 'backend',
          httpStatus: 503,
          code: 'root_missing',
          message: 'history root does not exist',
          details: { path: '/tmp/.copilot' },
        },
      } satisfies HistorySyncState,
      heading: '履歴の同期は完了しましたが、最新の一覧を表示できません',
    },
    {
      name: 'conflict',
      syncState: {
        status: 'conflict',
        error: {
          kind: 'backend',
          httpStatus: 409,
          code: 'history_sync_running',
          message: 'history sync is already running',
          details: { sync_run_id: 7 },
        },
      } satisfies HistorySyncState,
      heading: '履歴同期はすでに進行中の可能性があります',
    },
    {
      name: 'sync error',
      syncState: {
        status: 'sync_error',
        error: {
          kind: 'network',
          code: 'network_error',
          message: 'Network request failed',
          details: { cause: 'Failed to fetch' },
        },
      } satisfies HistorySyncState,
      heading: '履歴を同期できませんでした',
    },
  ])('renders the %s banner without hiding the current list', ({ syncState, heading }) => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult(syncState))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「keeps the existing session list visible while a sync is in progress」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「keeps the existing session list visible while a sync is in progress」の条件・入力・操作を実行する。
   * 期待値: the existing session list visible while a sync is in progress が維持されること。
   */
  it('keeps the existing session list visible while a sync is in progress', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'success',
      sessions: [buildSessionSummary()],
      meta: {
        count: 1,
        partial_results: false,
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({ status: 'syncing' }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '履歴を同期中...' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'session-123 を開く' })).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「shows sync failures separately from the initial index error state」を通じて、DB
   *   保存・validation・一意性制約を検証する。
   * テストケース: 「shows sync failures separately from the initial index error state」の条件・入力・操作を実行する。
   * 期待値: sync failures separately from the initial index error state が表示されること。
   */
  it('shows sync failures separately from the initial index error state', () => {
    mockedUseSessionIndex.mockReturnValue(buildUseSessionIndexResult({
      status: 'error',
      error: {
        kind: 'backend',
        httpStatus: 503,
        code: 'root_missing',
        message: 'history root does not exist',
        details: {
          path: '/tmp/.copilot',
        },
      },
    }))
    mockedUseHistorySync.mockReturnValue(buildUseHistorySyncResult({
      status: 'sync_error',
      error: {
        kind: 'backend',
        httpStatus: 500,
        code: 'history_sync_failed',
        message: 'history sync failed',
        details: {},
      },
    }))

    render(
      <MemoryRouter>
        <SessionIndexPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '履歴を同期できませんでした' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'セッション一覧を表示できません' })).toBeInTheDocument()
  })
})

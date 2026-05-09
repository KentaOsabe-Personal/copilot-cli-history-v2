import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { SessionApiError } from '../../../../src/features/sessions/api/sessionApi.types.ts'
import type { HistorySyncState } from '../../../../src/features/sessions/hooks/useHistorySync.ts'
import HistorySyncStatus from '../../../../src/features/sessions/components/HistorySyncStatus.tsx'

function buildSyncedResult() {
  return {
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
      degraded_count: 1,
    },
  }
}

function buildBackendError(overrides: Partial<Extract<SessionApiError, { kind: 'backend' }>> = {}): SessionApiError {
  return {
    kind: 'backend',
    httpStatus: 503,
    code: 'history_sync_failed',
    message: 'history sync failed',
    details: {},
    ...overrides,
  }
}

describe('HistorySyncStatus', () => {
  /**
   * 概要・目的: 「renders a compact success banner for synced sessions」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a compact success banner for synced sessions」の条件・入力・操作を実行する。
   * 期待値: a compact success banner for synced sessions が画面に表示されること。
   */
  it('renders a compact success banner for synced sessions', () => {
    const state: HistorySyncState = {
      status: 'synced_with_sessions',
      result: buildSyncedResult(),
    }

    render(<HistorySyncStatus state={state} />)

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('heading', { name: '履歴を最新化しました' })).toBeInTheDocument()
    expect(screen.getByText('3 件を保存しました。1 件は一部欠損を含みます。')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders a non-error empty outcome after a successful sync」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a non-error empty outcome after a successful sync」の条件・入力・操作を実行する。
   * 期待値: a non-error empty outcome after a successful sync が画面に表示されること。
   */
  it('renders a non-error empty outcome after a successful sync', () => {
    const state: HistorySyncState = {
      status: 'synced_empty',
      result: buildSyncedResult(),
    }

    render(<HistorySyncStatus state={state} />)

    expect(screen.getByRole('heading', { name: '履歴の同期は完了しました' })).toBeInTheDocument()
    expect(screen.getByText('取り込みは完了しましたが、表示できるセッションはまだありません。')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders a refresh error banner without presenting success state as
   *   current」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a refresh error banner without presenting success state as current」の条件・入力・操作を実行する。
   * 期待値: a refresh error banner without presenting success state as current が画面に表示されること。
   */
  it('renders a refresh error banner without presenting success state as current', () => {
    const state: HistorySyncState = {
      status: 'refresh_error',
      result: buildSyncedResult(),
      error: buildBackendError({ code: 'root_missing', message: 'history root does not exist' }),
    }

    render(<HistorySyncStatus state={state} />)

    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive')
    expect(
      screen.getByRole('heading', { name: '履歴の同期は完了しましたが、最新の一覧を表示できません' }),
    ).toBeInTheDocument()
    expect(screen.getByText('3 件を保存しましたが、一覧の再取得に失敗しました。時間をおいて再度お試しください。')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders a conflict banner when a sync is already running」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a conflict banner when a sync is already running」の条件・入力・操作を実行する。
   * 期待値: a conflict banner when a sync is already running が画面に表示されること。
   */
  it('renders a conflict banner when a sync is already running', () => {
    const state: HistorySyncState = {
      status: 'conflict',
      error: buildBackendError({
        httpStatus: 409,
        code: 'history_sync_running',
        message: 'history sync is already running',
      }),
    }

    render(<HistorySyncStatus state={state} />)

    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive')
    expect(screen.getByRole('heading', { name: '履歴同期はすでに進行中の可能性があります' })).toBeInTheDocument()
    expect(screen.getByText('少し時間をおいてから、もう一度お試しください。')).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「renders a retryable sync error banner for $label failures」を通じて、同期処理の状態管理と副作用を検証する。
   * テストケース: 「renders a retryable sync error banner for $label failures」の条件・入力・操作を実行する。
   * 期待値: a retryable sync error banner for $label failures が画面に表示されること。
   */
  it.each([
    {
      label: 'network',
      error: {
        kind: 'network',
        code: 'network_error',
        message: 'Network request failed',
        details: { cause: 'Failed to fetch' },
      } satisfies SessionApiError,
      expectedMessage: 'ネットワーク接続を確認してから再試行してください。',
    },
    {
      label: 'config',
      error: {
        kind: 'config',
        code: 'api_base_url_missing',
        message: 'VITE_API_BASE_URL is not configured',
        details: { env: 'VITE_API_BASE_URL' },
      } satisfies SessionApiError,
      expectedMessage: 'API 接続先の設定を確認してから再試行してください。',
    },
    {
      label: 'backend',
      error: buildBackendError(),
      expectedMessage: 'backend の状態を確認してから再試行してください。',
    },
  ])('renders a retryable sync error banner for $label failures', ({ error, expectedMessage }) => {
    const state: HistorySyncState = {
      status: 'sync_error',
      error,
    }

    render(<HistorySyncStatus state={state} />)

    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive')
    expect(screen.getByRole('heading', { name: '履歴を同期できませんでした' })).toBeInTheDocument()
    expect(screen.getByText(expectedMessage)).toBeInTheDocument()
  })

  /**
   * 概要・目的: 「does not render a banner for idle state」を通じて、hook の状態遷移と非同期制御を検証する。
   * テストケース: 「does not render a banner for idle state」の条件・入力・操作を実行する。
   * 期待値: render a banner for idle state しないこと。
   */
  it('does not render a banner for idle state', () => {
    render(<HistorySyncStatus state={{ status: 'idle' }} />)

    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })
})

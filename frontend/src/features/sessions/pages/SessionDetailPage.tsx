import { useParams } from 'react-router'

import ActivityTimeline from '../components/ActivityTimeline.tsx'
import ConversationTranscript from '../components/ConversationTranscript.tsx'
import DisclosureSection from '../components/DisclosureSection.tsx'
import IssueList from '../components/IssueList.tsx'
import SessionDetailHeader from '../components/SessionDetailHeader.tsx'
import StatusPanel from '../components/StatusPanel.tsx'
import { useSessionDetail } from '../hooks/useSessionDetail.ts'

function SessionDetailPage() {
  const sessionId = useParams().sessionId

  if (sessionId == null) {
    throw new Error('sessionId route param is required')
  }

  const { state, requestRaw } = useSessionDetail(sessionId)

  const activityEntries =
    state.status === 'success' ? state.detail.activity.entries : []
  const hasActivityWarning =
    state.status === 'success' &&
    activityEntries.some(
      (entry) => entry.degraded || entry.mapping_status === 'partial' || entry.issues.length > 0,
    )

  return (
    <section className="flex flex-col gap-6">
      <h2 className="text-2xl font-semibold text-white">セッション詳細</h2>
      <p className="min-w-0 break-all font-mono text-sm text-cyan-200">{sessionId}</p>

      {state.status === 'loading' ? (
        <StatusPanel
          variant="loading"
          title="セッション詳細を読み込んでいます"
          message="セッションのタイムラインを確認しています。"
        />
      ) : null}

      {state.status === 'not_found' ? (
        <StatusPanel
          variant="not_found"
          title="セッションが見つかりません"
          message="指定されたセッションは存在しないか、すでに参照できません。"
          showSessionIndexLink
        />
      ) : null}

      {state.status === 'error' ? (
        <StatusPanel
          variant="error"
          title="セッション詳細を表示できません"
          message="詳細の取得に失敗しました。セッション一覧に戻って対象を選び直してください。"
          showSessionIndexLink
        />
      ) : null}

      {state.status === 'success' ? (
        <>
          <SessionDetailHeader detail={state.detail} />
          <ConversationTranscript
            conversation={state.detail.conversation}
            stateScopeKey={`session:${state.detail.id}:conversation`}
          />
          {state.detail.issues.length > 0 ? (
            <DisclosureSection
              title="セッションの issue"
              summary={`${state.detail.issues.length} 件の session issue があります`}
              count={state.detail.issues.length}
              hasWarning={state.detail.degraded || state.detail.issues.length > 0}
            >
              <IssueList issues={state.detail.issues} />
            </DisclosureSection>
          ) : null}
          {activityEntries.length > 0 ? (
            <DisclosureSection
              title="内部 activity"
              summary={`${activityEntries.length} 件の補助 event を確認できます`}
              count={activityEntries.length}
              hasWarning={hasActivityWarning}
            >
              <ActivityTimeline
                activity={state.detail.activity}
                rawIncluded={state.detail.raw_included}
                rawStatus={state.rawStatus}
                onRequestRaw={requestRaw}
                stateScopeKey={`session:${state.detail.id}`}
              />
            </DisclosureSection>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

export default SessionDetailPage

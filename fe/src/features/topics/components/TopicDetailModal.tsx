import { TopicRoster } from './TopicRoster'
import { useAuth } from '../../auth/auth-context'
import { useTopicRoster } from '../useTopicRoster'
import { topicStatusLabel } from '../topic-api'
import { Modal } from '../../academic/components/Modal'
import type { TopicState } from '../useTopics'

export function TopicDetailModal({ state }: { state: TopicState }) {
  const { user, logout } = useAuth()
  const canCancel = user?.role === 1
  const canViewRoster = !state.detailLoading && !state.detailError && !!state.detail &&
    (user?.role === 1 || (user?.role === 2 && !!state.detail.advisor_id && state.detail.advisor_id === user.user_id))
  const roster = useTopicRoster(state.mode === 'detail' && canViewRoster ? state.selected?.topic_id : undefined, logout, state.retryDetail, canCancel)
  if (state.mode !== 'detail') return null
  const row = state.detail
  const canGrade = !state.detailLoading && !state.detailError && row?.status === 3 &&
    (user?.role === 1 || (user?.role === 2 && !!row.advisor_id && row.advisor_id === user.user_id))
  return <Modal title="Chi tiết đề tài" busy={roster.busy} onClose={state.close}>
    {state.detailLoading && <p role="status">Đang tải chi tiết đề tài…</p>}
    {state.detailError && <><p role="alert" className="academic-error">{state.detailError}</p><button type="button" onClick={state.retryDetail}>Tải lại chi tiết</button></>}
    {row && <dl className="topic-detail">
      <dt>GPA yêu cầu</dt><dd>{row.req_GPA}</dd>
      <dt>Chỉ tiêu sinh viên</dt><dd>{row.studentQuota}</dd>
      <dt>Mã đề tài</dt><dd>{row.topic_id}</dd>
      <dt>Tên đề tài</dt><dd>{row.name}</dd>
      <dt>Mô tả đề tài</dt><dd className="topic-detail-description">{row.description || '—'}</dd>
      <dt>Giáo viên hướng dẫn</dt><dd>{row.avisor_name || '—'}</dd>
      <dt>Tên ngành</dt><dd>{row.major_name || '—'}</dd>
      <dt>Tệp đính kèm</dt><dd>{row.file_url || '—'}</dd>
      <dt>Trạng thái</dt><dd>{topicStatusLabel(row.status)}</dd>
      <dt>Ngày tạo</dt><dd>{row.created_at || '—'}</dd>
      <dt>Cập nhật lần cuối</dt><dd>{row.updated_at || '—'}</dd>
      <dt>Người cập nhật</dt><dd>{row.updated_by || '—'}</dd>
    </dl>}
    {canViewRoster && <TopicRoster roster={roster} canCancel={canCancel} canGrade={canGrade} />}
    <div className="academic-actions"><button type="button" disabled={roster.busy} onClick={state.close}>Đóng</button></div>
  </Modal>
}

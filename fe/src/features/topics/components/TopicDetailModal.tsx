import { topicStatusLabel } from '../topic-api'
import { Modal } from '../../academic/components/Modal'
import type { TopicState } from '../useTopics'

export function TopicDetailModal({ state }: { state: TopicState }) {
  if (state.mode !== 'detail') return null
  const row = state.detail
  return <Modal title="Chi tiết đề tài" busy={false} onClose={state.close}>
    {state.detailLoading && <p role="status">Đang tải chi tiết đề tài…</p>}
    {state.detailError && <><p role="alert" className="academic-error">{state.detailError}</p><button type="button" onClick={state.retryDetail}>Tải lại chi tiết</button></>}
    {row && <dl className="topic-detail">
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
    <div className="academic-actions"><button type="button" onClick={state.close}>Đóng</button></div>
  </Modal>
}

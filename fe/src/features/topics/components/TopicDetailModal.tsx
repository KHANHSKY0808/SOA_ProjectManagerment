import { useAuth } from '../../auth/auth-context'
import { useTopicRoster } from '../useTopicRoster'
import { topicStatusLabel } from '../topic-api'
import { Modal } from '../../academic/components/Modal'
import type { TopicState } from '../useTopics'

export function TopicDetailModal({ state }: { state: TopicState }) {
  const { user, logout } = useAuth()
  const canViewRoster = user?.role === 1 || user?.role === 2
  const roster = useTopicRoster(state.mode === 'detail' && canViewRoster ? state.selected?.topic_id : undefined, logout)
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
    {canViewRoster && <section aria-label="Sinh viên đăng ký đề tài">
      <h3>Sinh viên đăng ký đề tài</h3>
      {roster.loading && <p role="status">Đang tải sinh viên đăng ký…</p>}
      {roster.error && <><p role="alert" className="academic-error">{roster.error}</p><button type="button" onClick={roster.retry}>Tải lại danh sách sinh viên</button></>}
      {roster.incomplete && <p className="academic-hint">Chưa tra cứu được đầy đủ họ tên. Danh sách đăng ký vẫn được hiển thị theo mã sinh viên.</p>}
      {roster.ready && !roster.rows.length && <p>Chưa có sinh viên đăng ký đề tài này.</p>}
      {!!roster.rows.length && <div className="academic-table"><table aria-label="Danh sách sinh viên đăng ký">
        <thead><tr><th scope="col">Mã sinh viên</th><th scope="col">Họ tên</th><th scope="col">Học kỳ</th><th scope="col">Ngày đăng ký</th></tr></thead>
        <tbody>{roster.rows.map(student => <tr key={student.registration_id}>
          <td>{student.student_id || 'Chưa xác định'}</td><td>{student.student_name || 'Chưa có tên'}</td>
          <td>{student.semester || '—'}</td><td>{student.created_at ? new Date(student.created_at).toLocaleString('vi-VN') : '—'}
          {student.status !== 1 && <span className="academic-hint"> (Cần kiểm tra trạng thái đăng ký)</span>}</td>
        </tr>)}</tbody>
      </table></div>}
      {roster.next && !roster.error && <button type="button" disabled={roster.loading} onClick={roster.more}>Xem thêm sinh viên</button>}
    </section>}
    <div className="academic-actions"><button type="button" onClick={state.close}>Đóng</button></div>
  </Modal>
}

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
    {canViewRoster && <section aria-label="Sinh viên đăng ký đề tài">
      <h3>Sinh viên đăng ký đề tài</h3>
      {roster.loading && <p role="status">Đang tải sinh viên đăng ký…</p>}
      {roster.error && <><p role="alert" className="academic-error">{roster.error}</p><button type="button" disabled={roster.busy || !!roster.selected} onClick={roster.retry}>Tải lại danh sách sinh viên</button></>}
      {roster.incomplete && <p className="academic-hint">Chưa tra cứu được đầy đủ họ tên. Danh sách đăng ký vẫn được hiển thị theo mã sinh viên.</p>}
      {roster.ready && !roster.rows.length && !roster.next && <p>Chưa có sinh viên đăng ký đề tài này.</p>}
      {!!roster.rows.length && <div className="academic-table"><table aria-label="Danh sách sinh viên đăng ký">
        <thead><tr><th scope="col">Mã sinh viên</th><th scope="col">Họ tên</th><th scope="col">Học kỳ</th><th scope="col">Ngày đăng ký</th><th scope="col">Điểm</th><th scope="col">Thao tác</th></tr></thead>
        <tbody>{roster.rows.map(student => <tr key={student.registration_id}>
          <td>{student.student_id || 'Chưa xác định'}</td><td>{student.student_name || 'Chưa có tên'}</td>
          <td>{student.semester || '—'}</td><td>{student.created_at ? new Date(student.created_at).toLocaleString('vi-VN') : '—'}
          {student.status !== 1 && <span className="academic-hint"> (Cần kiểm tra trạng thái đăng ký)</span>}</td>
          <td>{student.point ?? 'Chưa chấm'}</td>
          <td>{canGrade && <button type="button" aria-label={`Chấm điểm ${student.student_id || student.registration_id}`} disabled={roster.busy || roster.loading || !!roster.selected || !!roster.grading} onClick={() => roster.chooseGrade(student)}>{student.point === null ? 'Chấm điểm' : 'Sửa điểm'}</button>}{' '}
            {canCancel && <button type="button" className="topic-danger" aria-label={`Hủy đăng ký ${student.student_id || student.registration_id}`} disabled={roster.busy || roster.loading || !!roster.selected || !!roster.grading} onClick={() => roster.choose(student)}>Hủy đăng ký</button>}</td>
        </tr>)}</tbody>
      </table></div>}
      {roster.next && !roster.error && <button type="button" disabled={roster.loading || roster.busy || !!roster.selected || !!roster.grading} onClick={roster.more}>Xem thêm sinh viên</button>}
      {roster.notice && <p role="status" className="academic-success">{roster.notice}</p>}
      {roster.gradeError && !roster.grading && <p role="alert" className="academic-error">{roster.gradeError}</p>}
      {roster.grading && <form aria-label="Chấm điểm đăng ký" onSubmit={event => { event.preventDefault(); roster.saveGrade() }}>
        <p>Điểm cho sinh viên {roster.grading.student_name || roster.grading.student_id || roster.grading.registration_id}</p>
        <label>Điểm (0–10)<input type="number" min="0" max="10" step="0.01" value={roster.gradeDraft} disabled={roster.busy || roster.gradeUncertain} onChange={event => roster.setGradeDraft(event.target.value)} /></label>
        {roster.gradeError && <p role="alert" className="academic-error">{roster.gradeError}</p>}
        <div className="academic-actions">
          {roster.gradeUncertain ? <button type="button" disabled={roster.busy} onClick={roster.checkGrade}>{roster.busy ? 'Đang kiểm tra…' : 'Kiểm tra điểm'}</button>
            : <button type="submit" className="academic-primary" disabled={roster.busy}>{roster.busy ? 'Đang lưu…' : 'Lưu điểm'}</button>}
          <button type="button" disabled={roster.busy || roster.gradeUncertain} onClick={roster.backGrade}>Quay lại</button>
        </div>
      </form>}
      {canCancel && roster.selected && <div role="group" aria-label="Xác nhận hủy đăng ký">
        <p>Hủy đăng ký của sinh viên {roster.selected.student_name ? `${roster.selected.student_name} (${roster.selected.student_id || 'Chưa xác định'})` : roster.selected.student_id || roster.selected.registration_id} khỏi đề tài này?</p>
        {roster.actionError && <p role="alert" className="academic-error">{roster.actionError}</p>}
        <div className="academic-actions">
          {roster.uncertain ? <button type="button" disabled={roster.busy} onClick={roster.check}>{roster.busy ? 'Đang kiểm tra…' : 'Kiểm tra kết quả hủy'}</button>
            : <button type="button" className="topic-danger" disabled={roster.busy} onClick={roster.cancel}>{roster.busy ? 'Đang hủy…' : 'Xác nhận hủy đăng ký'}</button>}
          <button type="button" disabled={roster.busy || roster.uncertain} onClick={roster.back}>Quay lại</button>
        </div>
      </div>}
    </section>}
    <div className="academic-actions"><button type="button" disabled={roster.busy} onClick={state.close}>Đóng</button></div>
  </Modal>
}

import { useState } from 'react'
import { useAuth } from '../auth/auth-context'
import { Modal } from '../academic/components/Modal'
import { isCurrent } from './registration-api'
import { useStudentRegistrations } from './useStudentRegistrations'
import '../academic/academic.css'
import './registrations.css'

const time = (value: string | null) => value ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '—'

export function StudentRegistrationPage() {
  const { logout } = useAuth()
  const state = useStudentRegistrations(logout)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [historyFilter, setHistoryFilter] = useState('all')
  const rows = state.topics.filter(row => `${row.topic_id} ${row.name}`.toLocaleLowerCase('vi-VN').includes(search))
  const history = state.history.filter(row => historyFilter === 'all' || (historyFilter === 'active' ? isCurrent(row) : !isCurrent(row)))
  const topicName = (id: string | null) => state.topics.find(row => row.topic_id === id)?.name
  const disabled = !state.canAct || !!state.dialog

  return <div className="academic student-registration">
    <section className="dash-surface registration-intro" aria-label="Đăng ký đề tài tốt nghiệp">
      <div><p className="registration-eyebrow">ĐỒ ÁN TỐT NGHIỆP</p><h2>Chọn đề tài cho hành trình của bạn</h2>
        <p>Mỗi sinh viên đăng ký một đề tài đang mở thuộc khoa của mình. Bạn có thể hủy đăng ký để chọn lại.</p></div>
      <button type="button" disabled={state.busy || !!state.dialog} onClick={() => void state.reload()}>Tải lại</button>
    </section>
    {state.notice && <p role="status" className="academic-success">{state.notice}</p>}
    {state.uncertain && <section className="registration-warning" aria-label="Kiểm tra thao tác">
      <p>Kết quả thao tác chưa được xác nhận. Hãy kiểm tra lịch sử trước khi đăng ký hoặc hủy tiếp.</p>
      {!state.dialog && <button type="button" disabled={state.busy} onClick={() => void state.reconcile()}>Kiểm tra kết quả</button>}
    </section>}
    {!state.dialog && state.actionError && <p role="alert" className="academic-error">{state.actionError}</p>}

    <section className="dash-surface registration-current" aria-labelledby="registration-current-title">
      <div className="registration-heading"><h2 id="registration-current-title">Đăng ký hiện tại</h2><span className="registration-tag">Tối đa 1 đề tài</span></div>
      {state.historyLoading && <p role="status">Đang tải đăng ký…</p>}
      {state.historyError && <p role="alert" className="academic-error">{state.historyError} Tải lại để xác nhận đăng ký hiện tại.</p>}
      {state.historyReady && state.current.length === 0 && <p>Bạn chưa đăng ký đề tài. Chọn một đề tài trong danh sách bên dưới để bắt đầu.</p>}
      {state.current.length > 1 && <p role="alert" className="academic-error">Có nhiều đăng ký hiện tại. Vui lòng liên hệ bộ phận quản lý để kiểm tra dữ liệu.</p>}
      {state.current.map(row => <article className="registration-current-card" key={row.registration_id}>
        <div><span className="registration-code">{row.topic_id ?? 'Chưa có mã đề tài'}</span>
          {topicName(row.topic_id) && <h3>{topicName(row.topic_id)}</h3>}
          <p>Học kỳ: {row.semester || 'Không cung cấp'} · Đăng ký lúc: {time(row.created_at)} · Điểm: {row.point ?? 'Chưa chấm'}</p>
          <span className="registration-status">{row.status === 1 ? 'Đang đăng ký' : 'Cần kiểm tra trạng thái'}</span></div>
        <button type="button" className="registration-cancel" disabled={disabled} onClick={() => state.openCancel(row)} aria-label={`Hủy đăng ký ${row.topic_id ?? row.registration_id}`}>Hủy đăng ký</button>
      </article>)}
    </section>

    <section className="dash-surface" aria-labelledby="registration-topics-title">
      <div className="registration-heading"><div><h2 id="registration-topics-title">Đề tài mở đăng ký</h2><p className="academic-hint">Danh sách được lọc theo khoa của bạn.</p></div><span className="registration-tag">{state.topics.length} đề tài đã tải</span></div>
      <form role="search" aria-label="Tìm đề tài mở đăng ký" className="academic-search registration-search" onSubmit={event => { event.preventDefault(); setSearch(query.trim().toLocaleLowerCase('vi-VN')) }}>
        <label>Tìm trong đề tài đã tải<input type="search" placeholder="Mã hoặc tên đề tài" value={query} onChange={event => setQuery(event.target.value)} /></label>
        <button type="submit">Tìm kiếm</button>
      </form>
      {state.topicsLoading && <p role="status">Đang tải đề tài…</p>}
      {state.topicsError && <p role="alert" className="academic-error">{state.topicsError}</p>}
      {state.topicsReady && <div className="academic-table"><table aria-label="Đề tài mở đăng ký"><thead><tr><th>Mã đề tài</th><th>Tên đề tài</th><th>Thao tác</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.topic_id}><td className="registration-code">{row.topic_id}</td><td>{row.name}</td><td>
          <button type="button" className="academic-primary" disabled={disabled || state.current.length > 0} aria-label={`Đăng ký ${row.topic_id}`} onClick={() => state.openRegister(row)}>Đăng ký</button>
        </td></tr>)}{!rows.length && <tr><td colSpan={3}>{search ? 'Không có đề tài phù hợp trong các trang đã tải.' : state.nextAfter !== null
          ? 'Trang này chưa có đề tài thuộc khoa của bạn. Hãy tải thêm để xem tiếp.' : 'Chưa có đề tài mở đăng ký thuộc khoa của bạn.'}</td></tr>}</tbody></table></div>}
      {state.nextAfter !== null && <div className="registration-pagination"><p className="academic-hint">Tải thêm để xem các đề tài ở trang tiếp theo.</p><button type="button" disabled={state.topicsLoading || state.busy || !!state.dialog} onClick={() => void state.loadMore()}>Tải thêm đề tài</button></div>}
      {state.current.length > 0 && <p className="academic-hint">Bạn cần hủy đăng ký hiện tại trước khi đăng ký đề tài khác.</p>}
    </section>

    <section className="dash-surface" aria-labelledby="registration-history-title">
      <div className="registration-heading"><h2 id="registration-history-title">Lịch sử đăng ký</h2><label>Hiển thị<select aria-label="Lọc lịch sử" value={historyFilter} onChange={event => setHistoryFilter(event.target.value)}>
        <option value="all">Tất cả đăng ký</option><option value="active">Hiện tại</option><option value="cancelled">Đã hủy</option>
      </select></label></div>
      {state.historyReady || state.history.length > 0 ? <div className="academic-table"><table aria-label="Lịch sử đăng ký"><thead><tr><th>Mã đề tài</th><th>Học kỳ</th><th>Trạng thái</th><th>Điểm</th><th>Ngày đăng ký</th><th>Cập nhật</th></tr></thead>
        <tbody>{history.map(row => <tr key={row.registration_id}><td className="registration-code">{row.topic_id ?? '—'}</td><td>{row.semester || '—'}</td>
          <td><span className={`registration-status ${isCurrent(row) ? '' : 'is-cancelled'}`}>{row.status === 0 ? 'Đã hủy' : row.status === 1 ? 'Đang đăng ký' : 'Cần kiểm tra trạng thái'}</span></td>
          <td>{row.point ?? 'Chưa chấm'}</td><td>{time(row.created_at)}</td><td>{time(row.updated_at)}</td></tr>)}{!history.length && <tr><td colSpan={6}>Chưa có đăng ký trong danh sách này.</td></tr>}</tbody></table></div> : <p className="academic-hint">Lịch sử hiển thị sau khi tải đăng ký thành công.</p>}
    </section>

    {state.dialog && <Modal title={state.dialog.kind === 'register' ? 'Xác nhận đăng ký đề tài' : 'Xác nhận hủy đăng ký'} busy={state.busy} onClose={state.closeDialog}>
      <form aria-label={state.dialog.kind === 'register' ? 'Đăng ký đề tài' : 'Hủy đăng ký đề tài'} onSubmit={event => { event.preventDefault(); void state.submit() }}>
        {state.dialog.kind === 'register' ? <><p>Bạn chọn đề tài <strong>{state.dialog.topic.topic_id} · {state.dialog.topic.name}</strong>.</p>
          <label className="registration-semester">Học kỳ (không bắt buộc)<input value={state.semester} maxLength={255} disabled={state.busy || state.uncertain} placeholder="Ví dụ: 2026-1" onChange={event => state.setSemester(event.target.value)} /></label>
          <p className="academic-hint">Bạn chỉ có thể đăng ký một đề tài tại một thời điểm.</p></>
          : <p>Hủy đăng ký đề tài <strong>{state.dialog.registration.topic_id ?? state.dialog.registration.registration_id}</strong>? Đăng ký sẽ được lưu trong lịch sử và bạn có thể chọn lại đề tài.</p>}
        {state.actionError && <p role="alert" className="academic-error">{state.actionError}</p>}
        {state.uncertain && <><p className="academic-hint">Kết quả chưa rõ. Kiểm tra lịch sử trước khi thực hiện lại.</p>
          {state.historyError && <p role="alert" className="academic-error">{state.historyError}</p>}</>}
        <div className="academic-actions registration-dialog-actions"><button type="button" disabled={state.busy} onClick={state.closeDialog}>Đóng</button>
          {state.uncertain ? <button type="button" className="academic-primary" disabled={state.busy} onClick={() => void state.reconcile()}>{state.busy ? 'Đang kiểm tra…' : 'Kiểm tra kết quả'}</button>
            : <button type="submit" className={state.dialog.kind === 'register' ? 'academic-primary' : 'academic-danger'} disabled={!state.canAct}>{state.busy ? 'Đang xử lý…' : state.dialog.kind === 'register' ? 'Xác nhận đăng ký' : 'Xác nhận hủy'}</button>}
        </div>
      </form>
    </Modal>}
  </div>
}

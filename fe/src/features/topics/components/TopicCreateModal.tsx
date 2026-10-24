import { Modal } from '../../academic/components/Modal'
import { topicStatusLabels } from '../topic-api'
import { numericMajor } from '../useTopics'
import type { TopicField, TopicState } from '../useTopics'

export function TopicCreateModal({ state }: { state: TopicState }) {
  if (state.mode !== 'create' && state.mode !== 'edit') return null
  const editing = state.mode === 'edit'
  const title = editing ? 'Sửa đề tài' : 'Tạo đề tài'
  const error = (key: TopicField) => state.errors[key] && <span id={`topic-${key}-error`} className="academic-error">{state.errors[key]}</span>
  const accessibility = (key: TopicField) => ({ 'aria-invalid': !!state.errors[key], 'aria-describedby': state.errors[key] ? `topic-${key}-error` : undefined })
  return <Modal title={title} busy={state.busy} onClose={state.close}>
    {state.detailLoading && <p role="status">Đang tải chi tiết đề tài…</p>}
    {state.detailError && <><p role="alert" className="academic-error">{state.detailError}</p><button type="button" onClick={state.retryDetail}>Tải lại chi tiết</button></>}
    {state.draft && <form aria-label={title} noValidate onSubmit={event => {
      event.preventDefault()
      const form = event.currentTarget
      void state.save().then(key => { if (key) (form.elements.namedItem(key) as HTMLElement | null)?.focus() })
    }}>
      <p className="academic-hint">{editing ? `Mã đề tài: ${state.draft.topic_id} (không thể thay đổi).` : 'Mã đề tài được sinh tự động khi tạo.'}</p>
      {state.formError && <p role="alert" className="academic-error">{state.formError}</p>}
      {state.optionsLoading && <p role="status">Đang tải ngành và giảng viên…</p>}
      {state.optionsError && <p role="alert" className="academic-error">{state.optionsError}</p>}
      {!state.optionsReady && !state.optionsLoading && <button type="button" onClick={() => void state.loadOptions()}>Tải lại lựa chọn</button>}
      {!editing && state.optionsReady && (!state.lecturers.length || !state.majors.some(row => numericMajor(row.major_id))) && <p role="alert">Chưa có giảng viên hoặc ngành có mã số hợp lệ. Vui lòng bổ sung dữ liệu học vụ.</p>}
      <fieldset disabled={state.busy || state.uncertain}>
        <div className="academic-fields">
          <div><label htmlFor="topic-name">Tên đề tài</label><input id="topic-name" name="name" autoFocus={editing} required value={state.draft.name} onChange={event => state.change('name', event.target.value)} {...accessibility('name')} />{error('name')}</div>
          <div><label htmlFor="topic-req_GPA">GPA yêu cầu</label><input id="topic-req_GPA" name="req_GPA" type="number" min="0" max="4" step="any" required value={Number.isNaN(state.draft.req_GPA) ? '' : state.draft.req_GPA} onChange={event => state.change('req_GPA', event.target.value)} {...accessibility('req_GPA')} />{error('req_GPA')}</div>
          <div><label htmlFor="topic-studentQuota">Chỉ tiêu sinh viên</label><input id="topic-studentQuota" name="studentQuota" type="number" min="1" max="2147483647" step="1" required value={Number.isNaN(state.draft.studentQuota) ? '' : state.draft.studentQuota} onChange={event => state.change('studentQuota', event.target.value)} {...accessibility('studentQuota')} />{error('studentQuota')}</div>
          <div><label htmlFor="topic-advisor">Giáo viên hướng dẫn</label><select id="topic-advisor" name="advisor_id" required disabled={!state.optionsReady} value={state.draft.advisor_id} onChange={event => state.change('advisor_id', event.target.value)} {...accessibility('advisor_id')}>
            <option value="">Chọn giáo viên hướng dẫn</option>
            {editing && state.draft.advisor_id && !state.lecturers.some(row => row.lecturer_id === state.draft?.advisor_id) && <option value={state.draft.advisor_id}>{state.detail?.avisor_name || state.draft.advisor_id} (hiện tại)</option>}
            {state.lecturers.map(row => {
              const name = [row.user?.first_name, row.user?.last_name].filter(Boolean).join(' ')
              return <option key={row.lecturer_id} value={row.lecturer_id}>{name ? `${name} (${row.lecturer_id})` : row.lecturer_id}</option>
            })}
          </select>{error('advisor_id')}</div>
          <div><label htmlFor="topic-major">Ngành</label><select id="topic-major" name="major_id" required disabled={!state.optionsReady} value={state.draft.major_id} onChange={event => state.change('major_id', event.target.value)} {...accessibility('major_id')}>
            <option value="">Chọn ngành</option>
            {editing && !state.majors.some(row => row.major_id === state.draft?.major_id) && <option value={state.draft.major_id}>{state.detail?.major_name || state.draft.major_id} (hiện tại)</option>}
            {state.majors.map(row => <option key={row.major_id} value={row.major_id} disabled={!numericMajor(row.major_id)}>{row.name ? `${row.name} (${row.major_id})` : row.major_id}{!numericMajor(row.major_id) ? ' — Mã ngành chưa được hỗ trợ' : ''}</option>)}
          </select>{error('major_id')}</div>
          {state.canSetStatus && <div><label htmlFor="topic-status">Trạng thái</label><select id="topic-status" name="status" value={state.draft.status ?? ''} onChange={event => state.change('status', event.target.value)} {...accessibility('status')}>
            <option value="" disabled>Chọn trạng thái</option>
            {([0, 1, 2, 3] as const).map(status => <option key={status} value={status}>{topicStatusLabels[status]}</option>)}
          </select>{error('status')}</div>}
          <div className="topic-description"><label htmlFor="topic-description">Mô tả đề tài</label><textarea id="topic-description" name="description" rows={5} value={state.draft.description} onChange={event => state.change('description', event.target.value)} {...accessibility('description')} />{error('description')}</div>
        </div>
      </fieldset>
      <div className="academic-actions">
        {state.uncertain ? <button type="button" className="academic-primary" disabled={state.busy} onClick={() => void state.checkResult()}>{state.busy ? 'Đang kiểm tra…' : 'Kiểm tra kết quả'}</button>
          : <button type="submit" className="academic-primary" disabled={state.busy || !state.optionsReady}>{state.busy ? 'Đang lưu…' : editing ? 'Lưu thay đổi' : 'Tạo đề tài'}</button>}
        <button type="button" disabled={state.busy} onClick={state.close}>Hủy</button>
      </div>
    </form>}
    {!state.draft && <button type="button" onClick={state.close}>Hủy</button>}
  </Modal>
}

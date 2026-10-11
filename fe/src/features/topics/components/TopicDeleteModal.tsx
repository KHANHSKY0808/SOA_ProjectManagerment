import { Modal } from '../../academic/components/Modal'
import type { TopicState } from '../useTopics'

export function TopicDeleteModal({ state }: { state: TopicState }) {
  if (state.mode !== 'delete' || !state.selected) return null
  return <Modal title="Xóa đề tài" busy={state.busy} onClose={state.close}>
    <p>Bạn có chắc muốn xóa đề tài <strong>{state.selected.name}</strong> ({state.selected.topic_id})? Toàn bộ đăng ký liên quan, kể cả lịch sử đăng ký đã hủy, cũng sẽ bị xóa vĩnh viễn. Thao tác này không thể hoàn tác.</p>
    {state.formError && <p role="alert" className="academic-error">{state.formError}</p>}
    <div className="academic-actions">
      <button type="button" disabled={state.busy} onClick={state.close}>Hủy</button>
      {state.uncertain
        ? <button type="button" disabled={state.busy} onClick={() => void state.checkResult()}>{state.busy ? 'Đang kiểm tra…' : 'Kiểm tra kết quả'}</button>
        : <button type="button" className="topic-danger" disabled={state.busy} onClick={() => void state.remove()}>{state.busy ? 'Đang xóa…' : 'Xác nhận xóa'}</button>}
    </div>
  </Modal>
}

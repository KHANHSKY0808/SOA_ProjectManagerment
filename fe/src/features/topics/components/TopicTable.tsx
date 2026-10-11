import { topicStatusLabel } from '../topic-api'
import type { Topic } from '../topic-api'

export function TopicTable({ rows, total, canManage, disabled, onAction }: {
  rows: Topic[]; total: number; canManage: boolean; disabled: boolean
  onAction: (row: Topic, action: 'detail' | 'edit' | 'delete') => void
}) {
  return <>
    <p className="academic-count">Hiển thị {rows.length} / {total} đề tài</p>
    <div className="academic-table"><table aria-label="Danh sách đề tài">
      <thead><tr><th scope="col">Mã đề tài</th><th scope="col">Tên đề tài</th><th scope="col">Giáo viên hướng dẫn</th><th scope="col">Tên ngành</th><th scope="col">Trạng thái</th><th scope="col">Thao tác</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.topic_id}>
        <td>{row.topic_id}</td><td>{row.name}</td><td>{row.avisor_name || '—'}</td><td>{row.major_name || '—'}</td><td>{topicStatusLabel(row.status)}</td>
        <td><div className="academic-actions topic-row-actions">
          <button type="button" disabled={disabled} aria-label={`Xem chi tiết ${row.topic_id}`} onClick={() => onAction(row, 'detail')}>Chi tiết</button>
          {canManage && <>
            <button type="button" disabled={disabled} aria-label={`Sửa ${row.topic_id}`} onClick={() => onAction(row, 'edit')}>Sửa</button>
            <button type="button" disabled={disabled} className="topic-danger" aria-label={`Xóa ${row.topic_id}`} onClick={() => onAction(row, 'delete')}>Xóa</button>
          </>}
        </div></td>
      </tr>)}{rows.length === 0 && <tr><td colSpan={6}>Không có đề tài phù hợp.</td></tr>}</tbody>
    </table></div>
  </>
}

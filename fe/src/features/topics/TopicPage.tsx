import { useAuth } from '../auth/auth-context'
import { useTopics } from './useTopics'
import { TopicSearch } from './components/TopicSearch'
import { TopicTable } from './components/TopicTable'
import { TopicCreateModal } from './components/TopicCreateModal'
import { TopicDetailModal } from './components/TopicDetailModal'
import { TopicDeleteModal } from './components/TopicDeleteModal'
import '../academic/academic.css'
import './topics.css'

export function TopicPage() {
  const { user, logout } = useAuth()
  const canManage = user?.role === 1
  const canCreate = user?.role === 1 || user?.role === 2
  const state = useTopics(canManage, logout, user?.role === 1, canCreate, user?.role, user?.user_id)
  return <section className="academic dash-surface" aria-label="Quản lý đề tài">
    <div className="academic-toolbar">
      <TopicSearch query={state.query} onChange={state.setQuery} onSearch={state.search} />
      <div className="academic-actions">
        <button type="button" disabled={state.loading || state.busy || !!state.mode} onClick={() => void state.reload()}>Tải lại</button>
        {canCreate && <button type="button" className="academic-primary" disabled={state.busy || !!state.mode} onClick={state.open}>Tạo đề tài</button>}
      </div>
    </div>
    {state.notice && <p role="status" className="academic-success">{state.notice}</p>}
    {state.listError && <p role="alert" className="academic-error">{state.listError}</p>}
    {state.loading ? <p role="status">Đang tải đề tài…</p> : !state.listError && <TopicTable rows={state.rows} total={state.total} canManage={canManage} disabled={state.busy || !!state.mode} onAction={state.show} />}
    <TopicDetailModal state={state} />
    {canCreate && <TopicCreateModal state={state} />}
    {canManage && <TopicDeleteModal state={state} />}
  </section>
}

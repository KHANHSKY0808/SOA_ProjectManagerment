import { useCallback, useEffect, useState } from 'react'
import { normalizeApiError } from '../../services/api-error'
import { useAuth } from '../auth/auth-context'
import { getTopicDetail, listTopics, topicStatusLabel } from '../topics/topic-api'
import type { Topic, TopicDetail } from '../topics/topic-api'
import { useTopicRoster } from '../topics/useTopicRoster'
import { TopicRoster } from '../topics/components/TopicRoster'
import '../academic/academic.css'
import '../topics/topics.css'
import './registrations.css'

export function AdminRegistrationPage() {
  const { user, logout } = useAuth()
  const [topics, setTopics] = useState<Topic[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const allowed = user?.role === 1
  useEffect(() => {
    if (!allowed) return
    const controller = new AbortController()
    void listTopics(controller.signal).then(result => {
      if (controller.signal.aborted) return
      setTopics(result); setSelectedId(result[0]?.topic_id ?? '')
    }).catch(cause => {
      if (controller.signal.aborted) return
      if (normalizeApiError(cause).status === 401) logout()
      else setError('Không thể tải danh sách đề tài. Vui lòng thử lại.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [allowed, logout, attempt])
  if (!allowed) return <p role="alert">Bạn không có quyền quản lý đăng ký.</p>
  return <section className="academic dash-surface admin-registration" aria-label="Quản lý đăng ký">
    <p>Chọn đề tài để xem sinh viên đăng ký, hủy đăng ký hoặc chấm điểm.</p>
    {loading && <p role="status">Đang tải đề tài…</p>}
    {error && <><p role="alert">{error}</p><button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>Tải lại đề tài</button></>}
    {!loading && !error && !topics.length && <p>Chưa có đề tài để quản lý đăng ký.</p>}
    {!!topics.length && <RegistrationWorkspace key={selectedId} topics={topics} topicId={selectedId} onSelect={setSelectedId} logout={logout} />}
  </section>
}

function RegistrationWorkspace({ topics, topicId, onSelect, logout }: {
  topics: Topic[]; topicId: string; onSelect: (id: string) => void; logout: () => void
}) {
  const [detail, setDetail] = useState<TopicDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const refreshDetail = useCallback(() => { setLoading(true); setError(''); setAttempt(value => value + 1) }, [])
  const roster = useTopicRoster(topicId, logout, refreshDetail, true)
  const locked = roster.busy || !!roster.selected || !!roster.grading || roster.uncertain || roster.gradeUncertain
  useEffect(() => {
    const controller = new AbortController()
    void getTopicDetail(topicId, controller.signal).then(result => {
      if (!controller.signal.aborted) setDetail(result)
    }).catch(cause => {
      if (controller.signal.aborted) return
      if (normalizeApiError(cause).status === 401) logout()
      else setError('Không thể tải thông tin đề tài. Vui lòng thử lại.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [topicId, logout, attempt])
  const canGrade = !loading && !error && detail?.status === 3
  return <>
    <div className="registration-heading">
      <label htmlFor="registration-topic">Đề tài<select id="registration-topic" value={topicId} disabled={locked} onChange={event => { if (!locked) onSelect(event.target.value) }}>
        {topics.map(topic => <option key={topic.topic_id} value={topic.topic_id}>{topic.topic_id} — {topic.name}</option>)}
      </select></label>
      <button type="button" disabled={locked || loading || roster.loading} onClick={() => { refreshDetail(); roster.reload() }}>Tải lại</button>
    </div>
    {loading && <p role="status">Đang tải thông tin đề tài…</p>}
    {error && <><p role="alert">{error}</p><button type="button" disabled={locked} onClick={refreshDetail}>Tải lại thông tin đề tài</button></>}
    {!loading && !error && detail && <dl className="topic-detail">
      <dt>Mã đề tài</dt><dd>{detail.topic_id}</dd>
      <dt>Tên đề tài</dt><dd>{detail.name}</dd>
      <dt>Giáo viên hướng dẫn</dt><dd>{detail.avisor_name || 'Chưa có tên'}</dd>
      <dt>Ngành</dt><dd>{detail.major_name || 'Chưa xác định'}</dd>
      <dt>Trạng thái đề tài</dt><dd>{topicStatusLabel(detail.status)}</dd>
      <dt>GPA yêu cầu</dt><dd>{detail.req_GPA}</dd>
      <dt>Chỉ tiêu sinh viên</dt><dd>{detail.studentQuota}</dd>
    </dl>}
    {!loading && !error && detail?.status !== 3 && <p className="academic-hint">Chỉ có thể chấm điểm khi đề tài đã đóng đăng ký.</p>}
    <TopicRoster roster={roster} canCancel canGrade={canGrade} showRegistrationDetails />
  </>
}

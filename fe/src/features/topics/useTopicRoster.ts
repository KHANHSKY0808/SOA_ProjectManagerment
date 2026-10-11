import { useCallback, useEffect, useRef, useState } from 'react'
import { normalizeApiError } from '../../services/api-error'
import { getTopicRoster, cancelTopicRegistration, getTopicRegistrationState } from './roster-api'
import type { RegisteredStudent } from './roster-api'

export function useTopicRoster(topicId: string | undefined, logout: () => void) {
  const [rows, setRows] = useState<RegisteredStudent[]>([])
  const [next, setNext] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [incomplete, setIncomplete] = useState(false)
  const [ready, setReady] = useState(false)
  const active = useRef<AbortController | null>(null)
  const cursor = useRef('')
  const mutation = useRef<AbortController | null>(null)
  const locked = useRef(false)
  const [selected, setSelected] = useState<RegisteredStudent | null>(null)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async (after: string) => {
    if (!topicId || locked.current) return
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    cursor.current = after
    setLoading(true); setError('')
    try {
      const page = await getTopicRoster(topicId, after, controller.signal)
      if (controller.signal.aborted) return
      setRows(previous => after ? [...previous, ...page.results] : page.results)
      setNext(page.next_after); setIncomplete(previous => after ? previous || page.names_unavailable : page.names_unavailable)
      setReady(true)
    } catch (cause) {
      if (controller.signal.aborted) return
      const failure = normalizeApiError(cause)
      if (failure.status === 401) logout()
      else setError(failure.status === 403 ? 'Bạn không có quyền xem danh sách sinh viên.' : 'Không thể tải danh sách sinh viên đăng ký. Vui lòng thử lại.')
    } finally { if (!controller.signal.aborted) setLoading(false) }
  }, [topicId, logout])
  useEffect(() => {
    let disposed = false
    void Promise.resolve().then(() => {
      if (disposed) return
      setSelected(null); setBusy(false); setUncertain(false); setActionError(''); setNotice(''); locked.current = false
      setRows([]); setNext(null); setIncomplete(false); setReady(false); setError(''); setLoading(false)
      if (topicId) void load('')
    })
    return () => { disposed = true; active.current?.abort(); mutation.current?.abort() }
  }, [topicId, load])
  function choose(student: RegisteredStudent) {
    if (locked.current || uncertain || loading) return
    setSelected(student); setActionError(''); setNotice('')
  }
  function back() {
    if (locked.current || uncertain) return
    setSelected(null); setActionError('')
  }
  function completed(message: string, id: string) {
    setRows(previous => previous.filter(row => row.registration_id !== id))
    setSelected(null); setUncertain(false); setActionError(''); setNotice(message)
  }
  async function perform(checking: boolean) {
    if (!topicId || !selected || locked.current || loading || (uncertain && !checking)) return
    const student = selected
    locked.current = true; setBusy(true); setActionError('')
    active.current?.abort()
    const controller = new AbortController()
    mutation.current = controller
    try {
      if (checking) {
        const status = await getTopicRegistrationState(topicId, student.registration_id, controller.signal)
        if (controller.signal.aborted) return
        if (status === 0) completed('Đã xác nhận hủy đăng ký.', student.registration_id)
        else {
          setUncertain(false)
          setActionError('Đăng ký vẫn còn hiệu lực. Bạn có thể xác nhận hủy lại nếu cần.')
        }
      } else {
        await cancelTopicRegistration(topicId, student.registration_id, controller.signal)
        if (!controller.signal.aborted) completed('Đã hủy đăng ký sinh viên khỏi đề tài.', student.registration_id)
      }
    } catch (cause) {
      if (controller.signal.aborted) return
      const failure = normalizeApiError(cause)
      if (failure.status === 401) { logout(); return }
      if (failure.status === 404) { completed('Đăng ký không còn tồn tại trong đề tài.', student.registration_id); return }
      if (checking) {
        setActionError('Chưa kiểm tra được kết quả. Vui lòng kiểm tra lại trước khi hủy tiếp.')
        return
      }
      const ambiguous = ['network', 'timeout', 'unknown'].includes(failure.kind) || (failure.status ?? 0) >= 500
      setUncertain(ambiguous)
      setActionError(ambiguous ? 'Chưa xác định kết quả hủy đăng ký. Hãy kiểm tra kết quả trước khi thử lại.'
        : failure.status === 403 ? 'Bạn không có quyền hủy đăng ký này.' : 'Không thể hủy đăng ký. Vui lòng kiểm tra lại.')
    } finally {
      locked.current = false
      if (!controller.signal.aborted) setBusy(false)
    }
  }
  return { rows, loading, error, incomplete, ready, next, selected, busy, uncertain, actionError, notice,
    choose, back, cancel: () => { void perform(false) }, check: () => { void perform(true) },
    retry: () => { if (!selected && !uncertain) void load(cursor.current) },
    more: () => { if (next && !loading && !selected && !uncertain) void load(next) } }
}

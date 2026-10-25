import { useCallback, useEffect, useRef, useState } from 'react'
import { normalizeApiError } from '../../services/api-error'
import { cancelRegistration, getRegistrationTopicStatus, isCurrent, listAvailableTopics, listRegistrations, registerTopic } from './registration-api'
import type { AvailableTopic, RegisterInput, Registration } from './registration-api'
import { registrationError, requiresReconciliation } from './registration-errors'

type Dialog = { kind: 'register'; topic: AvailableTopic } | { kind: 'cancel'; registration: Registration }
type Pending = { kind: 'register'; input: RegisterInput } | { kind: 'cancel'; id: string }

export function useStudentRegistrations(logout: () => void) {
  const [history, setHistory] = useState<Registration[]>([])
  const [historyReady, setHistoryReady] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [topicStatuses, setTopicStatuses] = useState<Record<string, number | null>>({})
  const [topicStatusReady, setTopicStatusReady] = useState(false)
  const [topicStatusError, setTopicStatusError] = useState('')
  const [topics, setTopics] = useState<AvailableTopic[]>([])
  const [topicsLoading, setTopicsLoading] = useState(true)
  const [topicsReady, setTopicsReady] = useState(false)
  const [topicsError, setTopicsError] = useState('')
  const [nextAfter, setNextAfter] = useState<string | null>(null)
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const [semester, setSemester] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const historyRequest = useRef<AbortController | null>(null)
  const topicsRequest = useRef<AbortController | null>(null)
  const mutation = useRef<AbortController | null>(null)
  const locked = useRef(false)
  const pending = useRef<Pending | null>(null)

  const message = useCallback((cause: unknown) => {
    const error = normalizeApiError(cause)
    if (error.kind === 'cancelled') return ''
    if (error.status === 401) { logout(); return '' }
    return registrationError(error)
  }, [logout])

  const refreshHistory = useCallback(async (): Promise<Registration[] | null> => {
    historyRequest.current?.abort()
    const controller = new AbortController()
    historyRequest.current = controller
    setHistoryLoading(true); setHistoryReady(false); setHistoryError('')
    setTopicStatusReady(false); setTopicStatuses({}); setTopicStatusError('')
    try {
      const rows = await listRegistrations(controller.signal)
      if (controller.signal.aborted) return null
      setHistory(rows); setHistoryReady(true)
      const currentRows = rows.filter(isCurrent)
      const topicIds = [...new Set(currentRows.map(row => row.topic_id).filter((id): id is string => id !== null))]
      const results = await Promise.allSettled(topicIds.map(async id => [id, await getRegistrationTopicStatus(id, controller.signal)] as const))
      if (controller.signal.aborted) return null
      const statuses: Record<string, number | null> = {}
      results.forEach(result => { if (result.status === 'fulfilled') statuses[result.value[0]] = result.value[1] })
      setTopicStatuses(statuses)
      const failed = results.find(result => result.status === 'rejected')
      if (failed || currentRows.some(row => row.topic_id === null)) {
        setTopicStatusError(failed ? message(failed.reason) : 'Không thể xác minh trạng thái đề tài. Vui lòng tải lại.')
      } else setTopicStatusReady(true)
      return rows
    } catch (cause) {
      if (!controller.signal.aborted) setHistoryError(message(cause))
      return null
    } finally {
      if (!controller.signal.aborted) { setHistoryLoading(false); historyRequest.current = null }
    }
  }, [message])

  const loadTopics = useCallback(async (after = '', append = false) => {
    if (append && topicsRequest.current) return
    topicsRequest.current?.abort()
    const controller = new AbortController()
    topicsRequest.current = controller
    setTopicsLoading(true); setTopicsError('')
    if (!append) { setTopics([]); setTopicsReady(false); setNextAfter(null) }
    try {
      const page = await listAvailableTopics(after, controller.signal)
      if (controller.signal.aborted) return
      setTopics(previous => {
        const rows = append ? [...previous, ...page.results] : page.results
        return [...new Map(rows.map(row => [row.topic_id, row])).values()]
      })
      setNextAfter(page.next_after); setTopicsReady(true)
    } catch (cause) {
      if (!controller.signal.aborted) setTopicsError(message(cause))
    } finally {
      if (!controller.signal.aborted) { setTopicsLoading(false); topicsRequest.current = null }
    }
  }, [message])

  useEffect(() => {
    let disposed = false
    void Promise.resolve().then(() => {
      if (!disposed) { void refreshHistory(); void loadTopics() }
    })
    return () => {
      disposed = true
      historyRequest.current?.abort(); topicsRequest.current?.abort(); mutation.current?.abort()
    }
  }, [refreshHistory, loadTopics])

  const current = history.filter(isCurrent)
  const canAct = historyReady && !historyLoading && !busy && !uncertain
  const canCancel = (registration: Registration) => canAct && isCurrent(registration) && topicStatusReady &&
    registration.topic_id !== null && Object.hasOwn(topicStatuses, registration.topic_id) && topicStatuses[registration.topic_id] !== 3
  function openRegister(topic: AvailableTopic) {
    if (!canAct || current.length || locked.current || !topic.eligible) return
    setSemester(''); setActionError(''); setNotice(''); setDialog({ kind: 'register', topic })
  }
  function openCancel(registration: Registration) {
    if (!canCancel(registration) || locked.current) return
    setActionError(''); setNotice(''); setDialog({ kind: 'cancel', registration })
  }
  function closeDialog() { if (!locked.current) setDialog(null) }

  async function submit() {
    if (!dialog || !canAct || locked.current) return
    if (dialog.kind === 'register' && (current.length || !dialog.topic.eligible)) return
    if (dialog.kind === 'cancel' && !canCancel(dialog.registration)) return
    const action: Pending = dialog.kind === 'register'
      ? { kind: 'register', input: { topic_id: dialog.topic.topic_id, ...(semester.trim() ? { semester: semester.trim() } : {}) } }
      : { kind: 'cancel', id: dialog.registration.registration_id }
    if (action.kind === 'register' && (action.input.semester?.length ?? 0) > 255) {
      setActionError('Học kỳ không được vượt quá 255 ký tự.'); return
    }
    locked.current = true; setBusy(true); setActionError(''); setNotice('')
    // A pre-write read must never restore stale state after a mutation.
    historyRequest.current?.abort()
    const controller = new AbortController()
    mutation.current = controller
    try {
      if (action.kind === 'register') {
        const row = await registerTopic(action.input, controller.signal)
        if (controller.signal.aborted) return
        setHistory(rows => [row, ...rows.filter(existing => existing.registration_id !== row.registration_id)])
        setNotice('Đăng ký đề tài thành công.')
      } else {
        await cancelRegistration(action.id, controller.signal)
        if (controller.signal.aborted) return
        setHistory(rows => rows.map(row => row.registration_id === action.id ? { ...row, status: 0, updated_at: null } : row))
        setNotice('Đã hủy đăng ký đề tài.')
      }
      setDialog(null)
      await Promise.all([refreshHistory(), loadTopics()])
    } catch (cause) {
      if (controller.signal.aborted) return
      const failure = normalizeApiError(cause)
      setActionError(message(failure))
      if (action.kind === 'register' && failure.details && typeof failure.details === 'object' &&
          'code' in failure.details && ['gpa_requirement_not_met', 'topic_quota_full'].includes(String(failure.details.code))) {
        setDialog(null)
        void loadTopics()
      }
      if (action.kind === 'cancel' && failure.status === 409 && failure.details && typeof failure.details === 'object' &&
          'code' in failure.details && failure.details.code === 'topic_registration_closed') {
        setDialog(null)
        void refreshHistory()
      } else if (failure.status !== 401 && requiresReconciliation(failure, action.kind === 'cancel')) {
        pending.current = action; setUncertain(true); setHistoryReady(false)
      }
    } finally {
      if (!controller.signal.aborted) { locked.current = false; setBusy(false); mutation.current = null }
    }
  }

  async function reconcile() {
    if (locked.current || !pending.current) return
    locked.current = true; setBusy(true); setActionError('')
    const action = pending.current
    try {
      const rows = await refreshHistory()
      if (!rows) return
      if (action.kind === 'register') {
        const match = rows.find(row => isCurrent(row) && row.topic_id === action.input.topic_id && row.semester === (action.input.semester ?? null))
        setNotice(match ? 'Đã xác nhận đăng ký đề tài thành công.' : rows.some(isCurrent)
          ? 'Bạn đang có đăng ký hiện tại. Vui lòng kiểm tra thông tin bên dưới.'
          : 'Chưa có đăng ký hiện tại. Bạn có thể chọn đăng ký lại.')
      } else {
        const stillCurrent = rows.some(row => row.registration_id === action.id && isCurrent(row))
        setNotice(stillCurrent ? 'Đăng ký vẫn còn hiệu lực. Bạn có thể hủy lại.' : 'Đăng ký này không còn hiệu lực.')
      }
      pending.current = null; setUncertain(false); setDialog(null)
    } finally {
      locked.current = false; setBusy(false)
    }
  }

  async function reload() {
    if (locked.current || dialog) return
    if (pending.current) { await reconcile(); return }
    await Promise.all([refreshHistory(), loadTopics()])
  }

  return { history, current, historyReady, historyLoading, historyError, topicStatuses, topicStatusReady, topicStatusError,
    canCancel, topics, topicsLoading, topicsReady,
    topicsError, nextAfter, dialog, semester, setSemester, actionError, notice, busy, uncertain, canAct,
    openRegister, openCancel, closeDialog, submit, reconcile, reload,
    loadMore: () => nextAfter !== null ? loadTopics(nextAfter, true) : Promise.resolve() }
}

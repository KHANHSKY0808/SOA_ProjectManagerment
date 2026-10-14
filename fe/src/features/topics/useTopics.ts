import { useCallback, useEffect, useRef, useState } from 'react'
import { normalizeApiError } from '../../services/api-error'
import { listRecords } from '../academic/academic-api'
import type { Lecturer, Major } from '../academic/academic-api'
import { createTopic, deleteTopic, getTopic, getTopicDetail, listTopics, updateTopic } from './topic-api'
import type { CreateTopic, Topic, TopicDetail, TopicUpdate, TopicStatus } from './topic-api'
import { createTopicId } from './topic-id'

export type TopicField = 'status' | 'name' | 'description' | 'advisor_id' | 'major_id'
export const numericMajor = (id: string) => /^[0-9]+$/.test(id)
type DialogMode = 'create' | 'detail' | 'edit' | 'delete' | null
const fields = ['name', 'description', 'advisor_id', 'major_id'] as const
const ambiguousWrite = (cause: unknown) => {
  const failure = normalizeApiError(cause)
  return failure.kind === 'network' || failure.kind === 'timeout' || failure.kind === 'unknown' || (failure.status ?? 0) >= 500
}

export function useTopics(canManage: boolean, logout: () => void, canSetStatus = false) {
  const [rows, setRows] = useState<Topic[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [mode, setMode] = useState<DialogMode>(null)
  const [selected, setSelected] = useState<Topic | null>(null)
  const [detail, setDetail] = useState<TopicDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [draft, setDraft] = useState<CreateTopic | null>(null)
  const [majors, setMajors] = useState<Major[]>([])
  const [lecturers, setLecturers] = useState<Lecturer[]>([])
  const [optionsReady, setOptionsReady] = useState(false)
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [optionsError, setOptionsError] = useState('')
  const [formError, setFormError] = useState('')
  const [errors, setErrors] = useState<Partial<Record<TopicField, string>>>({})
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [notice, setNotice] = useState('')
  const locked = useRef(false)
  const original = useRef<CreateTopic | null>(null)
  const pendingPatch = useRef<TopicUpdate>({})
  const loadRequest = useRef<AbortController | null>(null)
  const optionsRequest = useRef<AbortController | null>(null)
  const detailRequest = useRef<AbortController | null>(null)
  const mutation = useRef<AbortController | null>(null)

  const failureMessage = useCallback((cause: unknown) => {
    const failure = normalizeApiError(cause)
    if (failure.kind === 'cancelled') return ''
    if (failure.status === 401) { logout(); return '' }
    if (failure.status === 503) return 'Dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau.'
    if (failure.status === 409) return 'Mã đề tài đã tồn tại hoặc dữ liệu còn liên kết. Vui lòng kiểm tra kết quả.'
    return failure.message
  }, [logout])

  const reload = useCallback(async () => {
    loadRequest.current?.abort()
    const controller = new AbortController()
    loadRequest.current = controller
    setLoading(true); setListError('')
    try {
      const result = await listTopics(controller.signal)
      if (!controller.signal.aborted) setRows(result)
    } catch (cause) {
      if (!controller.signal.aborted) setListError(failureMessage(cause))
    } finally { if (!controller.signal.aborted) setLoading(false) }
  }, [failureMessage])

  useEffect(() => {
    let disposed = false
    void Promise.resolve().then(() => { if (!disposed) return reload() })
    return () => {
      disposed = true
      loadRequest.current?.abort(); optionsRequest.current?.abort(); detailRequest.current?.abort(); mutation.current?.abort()
    }
  }, [reload])

  async function loadOptions() {
    optionsRequest.current?.abort()
    const controller = new AbortController()
    optionsRequest.current = controller
    setOptionsReady(false); setOptionsLoading(true); setOptionsError('')
    try {
      const [courses, advisors] = await Promise.all([
        listRecords('majors', controller.signal), listRecords('lecturers', controller.signal),
      ])
      if (controller.signal.aborted) return
      setMajors(courses); setLecturers(advisors); setOptionsReady(true)
    } catch (cause) {
      if (!controller.signal.aborted) setOptionsError(failureMessage(cause))
    } finally { if (!controller.signal.aborted) setOptionsLoading(false) }
  }

  function resetForm() {
    setErrors({}); setFormError(''); setUncertain(false); setNotice('')
    setDetail(null); setDetailError(''); setDraft(null); original.current = null
  }
  function open() {
    if (!canManage || locked.current || mode) return
    try {
      const id = createTopicId()
      resetForm(); setMode('create'); setSelected(null)
      setDraft({ topic_id: id, name: '', description: '', advisor_id: '', major_id: '', ...(canSetStatus ? { status: 1 as const } : {}) })
      void loadOptions()
    } catch {
      setListError('Không thể sinh mã đề tài. Vui lòng thử lại hoặc cập nhật trình duyệt.')
    }
  }
  async function loadDetail(row: Topic, editing: boolean) {
    detailRequest.current?.abort()
    const controller = new AbortController()
    detailRequest.current = controller
    setDetailLoading(true); setDetailError('')
    try {
      const result = await getTopicDetail(row.topic_id, controller.signal)
      if (controller.signal.aborted) return
      if (editing) {
        if (typeof result.major_id !== 'string' || !result.major_id ||
            !(result.advisor_id === null || typeof result.advisor_id === 'string')) throw new Error('Missing management references')
        const value: CreateTopic = { topic_id: result.topic_id, name: result.name, description: result.description ?? '',
          major_id: result.major_id, advisor_id: result.advisor_id ?? '', ...(canSetStatus && (result.status === 0 || result.status === 1 || result.status === 2 || result.status === 3) ? { status: result.status } : {}) }
        original.current = value; setDraft(value)
      }
      setDetail(result)
    } catch (cause) {
      if (!controller.signal.aborted) setDetailError(failureMessage(cause))
    } finally { if (!controller.signal.aborted) setDetailLoading(false) }
  }
  function show(row: Topic, next: 'detail' | 'edit' | 'delete') {
    if (locked.current || mode || (next !== 'detail' && !canManage)) return
    resetForm(); setSelected(row); setMode(next)
    if (next !== 'delete') void loadDetail(row, next === 'edit')
    if (next === 'edit') void loadOptions()
  }
  function retryDetail() {
    if (selected && !locked.current) void loadDetail(selected, mode === 'edit')
  }
  function dismiss() {
    optionsRequest.current?.abort(); detailRequest.current?.abort()
    setMode(null); setSelected(null); setDetail(null); setDetailError(''); setDetailLoading(false)
    setDraft(null); setErrors({}); setFormError(''); setUncertain(false)
  }
  function close() {
    if (!locked.current) dismiss()
  }
  function change(key: TopicField, value: string) {
    if (locked.current || uncertain || (key === 'status' && !canSetStatus)) return
    setDraft(previous => previous && { ...previous, [key]: key === 'status' ? (value === '' ? undefined : Number(value) as TopicStatus) : value })
    setErrors(previous => ({ ...previous, [key]: undefined }))
  }
  async function saved(message: string) {
    dismiss(); setNotice(message)
    await reload()
  }
  async function save(): Promise<TopicField | undefined> {
    if (!canManage || !draft || locked.current || !optionsReady || uncertain || (mode !== 'create' && mode !== 'edit')) return
    const editing = mode === 'edit'
    const values = { ...draft, name: draft.name.trim() }
    const changed = (key: TopicField) => !editing || values[key] !== original.current?.[key]
    const invalid: Partial<Record<TopicField, string>> = {}
    if (!values.name) invalid.name = 'Vui lòng nhập tên đề tài.'
    if (changed('advisor_id') && !lecturers.some(row => row.lecturer_id === draft.advisor_id)) invalid.advisor_id = 'Vui lòng chọn giáo viên hướng dẫn.'
    if (changed('major_id') && (!majors.some(row => row.major_id === draft.major_id) || !numericMajor(draft.major_id))) invalid.major_id = 'Vui lòng chọn ngành có mã số hợp lệ.'
    if (canSetStatus && (!editing || changed('status')) && ![0, 1, 2, 3].includes(values.status as number)) invalid.status = 'Vui lòng chọn trạng thái hợp lệ.'
    setErrors(invalid)
    const first = Object.keys(invalid)[0] as TopicField | undefined
    if (first) return first
    const patch: TopicUpdate = {}
    for (const key of fields) if (changed(key)) patch[key] = key === 'description' ? values[key].trim() : values[key]
    if (canSetStatus && changed('status') && values.status !== undefined) patch.status = values.status
    if (editing && !Object.keys(patch).length) { close(); setNotice('Không có thay đổi.'); return }
    pendingPatch.current = patch
    locked.current = true; setBusy(true); setFormError('')
    const controller = new AbortController()
    mutation.current = controller
    try {
      if (editing) await updateTopic(draft.topic_id, patch, controller.signal)
      else {
        const { status, ...input } = values
        await createTopic(canSetStatus ? { ...input, status } : input, controller.signal)
      }
      if (!controller.signal.aborted) {
        await saved(editing ? 'Đã cập nhật đề tài.' : 'Đã tạo đề tài.')
      }
    } catch (cause) {
      if (controller.signal.aborted) return
      const failure = normalizeApiError(cause)
      const ambiguous = ambiguousWrite(cause) || (!editing && failure.status === 409)
      setUncertain(ambiguous)
      const message = failureMessage(cause)
      setFormError(ambiguous ? `${message} Chưa xác định kết quả ${editing ? 'cập nhật' : 'tạo'}. Hãy kiểm tra kết quả trước khi gửi lại.` : message)
      if (failure.status === 400 && failure.details && typeof failure.details === 'object') {
        const details = failure.details as Record<string, unknown>
        const next: Partial<Record<TopicField, string>> = {}
        for (const key of [...fields, 'status'] as const) if (key in details) next[key] = 'Giá trị không hợp lệ. Vui lòng kiểm tra lại.'
        setErrors(next)
        return Object.keys(next)[0] as TopicField | undefined
      }
    } finally { locked.current = false; if (!controller.signal.aborted) setBusy(false) }
  }
  async function remove() {
    if (!canManage || mode !== 'delete' || !selected || locked.current || uncertain) return
    locked.current = true; setBusy(true); setFormError('')
    const controller = new AbortController()
    mutation.current = controller
    try {
      await deleteTopic(selected.topic_id, controller.signal)
      if (!controller.signal.aborted) await saved('Đã xóa đề tài.')
    } catch (cause) {
      if (controller.signal.aborted) return
      const failure = normalizeApiError(cause)
      if (failure.status === 404) { await saved('Đề tài không còn tồn tại.'); return }
      if (failure.status === 409) { setUncertain(true); setFormError('Dữ liệu liên kết đã thay đổi. Đăng ký có thể đã bị xóa vĩnh viễn. Hãy kiểm tra kết quả trước khi xác nhận xóa lại.') }
      else {
        const ambiguous = ambiguousWrite(cause)
        setUncertain(ambiguous)
        const message = failureMessage(cause)
        setFormError(ambiguous ? `${message} Chưa xác định kết quả xóa. Đề tài có thể đã đóng và đăng ký liên quan có thể đã bị xóa vĩnh viễn. Hãy kiểm tra kết quả trước khi thử lại.` : message)
      }
    } finally { locked.current = false; if (!controller.signal.aborted) setBusy(false) }
  }
  async function checkResult() {
    const id = draft?.topic_id ?? selected?.topic_id
    if (!canManage || !id || !uncertain || locked.current) return
    locked.current = true; setBusy(true); setFormError('')
    const controller = new AbortController()
    mutation.current = controller
    try {
      const result = mode === 'edit' ? await getTopicDetail(id, controller.signal) : await getTopic(id, controller.signal)
      if (controller.signal.aborted) return
      if (mode === 'delete') {
        setUncertain(false); setFormError('Đề tài vẫn tồn tại; đăng ký liên quan có thể đã bị xóa vĩnh viễn. Đề tài có thể đang đóng đăng ký. Bạn có thể xác nhận xóa lại nếu cần.')
      } else if (mode === 'edit') {
        const current = result as TopicDetail
        const matches = Object.entries(pendingPatch.current).every(([key, value]) =>
          (current[key as TopicField] ?? '') === value)
        if (matches) await saved('Đã xác nhận dữ liệu cập nhật.')
        else {
          setUncertain(false)
          setFormError('Dữ liệu hiện tại chưa khớp bản sửa. Hãy xem lại hoặc đóng và tải lại đề tài trước khi lưu lại.')
        }
      } else await saved('Đã tạo đề tài.')
    } catch (cause) {
      if (controller.signal.aborted) return
      if (normalizeApiError(cause).status === 404) {
        if (mode === 'delete') await saved('Đã xác nhận đề tài không còn tồn tại.')
        else if (mode === 'create') {
          setUncertain(false)
          setFormError('Chưa tìm thấy đề tài với mã này. Bạn có thể kiểm tra dữ liệu và gửi lại với cùng mã.')
        } else setFormError('Đề tài không còn tồn tại. Đóng popup và tải lại danh sách.')
      } else setFormError(failureMessage(cause))
    } finally { locked.current = false; if (!controller.signal.aborted) setBusy(false) }
  }
  const normalized = appliedQuery.toLocaleLowerCase('vi')
  const visibleRows = rows.filter(row => [row.topic_id, row.name].some(value => value.toLocaleLowerCase('vi').includes(normalized)))
  return { rows: visibleRows, total: rows.length, loading, listError, query, setQuery,
    search: () => setAppliedQuery(query.trim()), reload, mode, selected, detail, detailLoading, detailError, retryDetail,
    canSetStatus, draft, majors, lecturers, optionsReady, optionsLoading, optionsError, loadOptions, formError, errors, busy,
    uncertain, notice, open, show, close, change, save, remove, checkResult }
}
export type TopicState = ReturnType<typeof useTopics>

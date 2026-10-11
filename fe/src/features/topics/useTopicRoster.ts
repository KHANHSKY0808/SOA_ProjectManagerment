import { useCallback, useEffect, useRef, useState } from 'react'
import { normalizeApiError } from '../../services/api-error'
import { getTopicRoster } from './roster-api'
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
  const load = useCallback(async (after: string) => {
    if (!topicId) return
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
      setRows([]); setNext(null); setIncomplete(false); setReady(false); setError(''); setLoading(false)
      if (topicId) void load('')
    })
    return () => { disposed = true; active.current?.abort() }
  }, [topicId, load])
  return { rows, loading, error, incomplete, ready, next,
    retry: () => { void load(cursor.current) },
    more: () => { if (next && !loading) void load(next) } }
}

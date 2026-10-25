import { apiClient } from '../../services/api-client'

export interface RegisteredStudent {
  registration_id: string
  student_id: string | null
  student_name: string | null
  semester: string | null
  status: number | null
  created_at: string | null
  point: string | null
}
export interface RosterPage { results: RegisteredStudent[]; next_after: string | null; names_unavailable: boolean }
export async function getTopicRoster(id: string, after: string, signal: AbortSignal): Promise<RosterPage> {
  const path = `/registrations/api/v1/topics/${encodeURIComponent(id)}/registrations/${after ? `?after=${encodeURIComponent(after)}` : ''}`
  const { data } = await apiClient.get<unknown>(path, { signal })
  if (!data || typeof data !== 'object') throw new Error('Invalid topic roster')
  const page = data as RosterPage
  if (!Array.isArray(page.results) || page.results.length > 100 || typeof page.names_unavailable !== 'boolean') throw new Error('Invalid topic roster')
  let previous = after
  for (const row of page.results) {
    if (!row || typeof row.registration_id !== 'string' || row.registration_id <= previous ||
        !['student_id', 'student_name', 'semester', 'created_at'].every(key => {
          const value = row[key as keyof RegisteredStudent]
          return value === null || typeof value === 'string'
        }) || !(row.status === null || (Number.isInteger(row.status) && row.status !== 0)) || !validPoint(row.point)) throw new Error('Invalid topic roster')
    if (row.created_at !== null && !Number.isFinite(Date.parse(row.created_at))) throw new Error('Invalid registration date')
    previous = row.registration_id
  }
  if (page.next_after !== null && (typeof page.next_after !== 'string' || page.results.length !== 100 || page.next_after !== previous)) throw new Error('Invalid roster cursor')
  // Explicit projection keeps private fields out of UI state.
  return { results: page.results.map(({ registration_id, student_id, student_name, semester, status, created_at, point }) =>
    ({ registration_id, student_id, student_name, semester, status, created_at, point })), next_after: page.next_after, names_unavailable: page.names_unavailable }
}

const validPoint = (value: unknown): value is string | null => value === null ||
  (typeof value === 'string' && /^(?:\d|10)\.\d{2}$/.test(value) && Number(value) <= 10)


const registrationPath = (topicId: string, registrationId: string) =>
  `/registrations/api/v1/topics/${encodeURIComponent(topicId)}/registrations/${encodeURIComponent(registrationId)}/`

export async function cancelTopicRegistration(topicId: string, registrationId: string, signal: AbortSignal): Promise<void> {
  const response = await apiClient.delete(registrationPath(topicId, registrationId), { signal })
  if (response.status !== 204) throw new Error('Invalid cancellation response')
}

export async function getTopicRegistrationDetail(topicId: string, registrationId: string, signal: AbortSignal): Promise<{status: number | null; point: string | null}> {
  const { data } = await apiClient.get<unknown>(registrationPath(topicId, registrationId), { signal })
  if (!data || typeof data !== 'object') throw new Error('Invalid registration state')
  const row = data as Record<string, unknown>
  if (row.topic_id !== topicId || row.registration_id !== registrationId ||
      !(row.status === null || Number.isInteger(row.status)) || !validPoint(row.point)) throw new Error('Invalid registration state')
  return { status: row.status as number | null, point: row.point }
}

export async function getTopicRegistrationState(topicId: string, registrationId: string, signal: AbortSignal): Promise<number | null> {
  return (await getTopicRegistrationDetail(topicId, registrationId, signal)).status
}

export async function gradeTopicRegistration(topicId: string, registrationId: string, point: string, signal: AbortSignal): Promise<string> {
  const { data, status } = await apiClient.put<unknown>(registrationPath(topicId, registrationId) + 'point/', { point }, { signal })
  if (status !== 200 || !data || typeof data !== 'object') throw new Error('Invalid grading response')
  const row = data as Record<string, unknown>
  if (row.topic_id !== topicId || row.registration_id !== registrationId || !validPoint(row.point) || row.point === null ||
      !(typeof row.updated_at === 'string' && Number.isFinite(Date.parse(row.updated_at)))) throw new Error('Invalid grading response')
  return row.point
}

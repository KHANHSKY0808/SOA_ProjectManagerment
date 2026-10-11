import { apiClient } from '../../services/api-client'

export interface RegisteredStudent {
  registration_id: string
  student_id: string | null
  student_name: string | null
  semester: string | null
  status: number | null
  created_at: string | null
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
        }) || !(row.status === null || (Number.isInteger(row.status) && row.status !== 0))) throw new Error('Invalid topic roster')
    if (row.created_at !== null && !Number.isFinite(Date.parse(row.created_at))) throw new Error('Invalid registration date')
    previous = row.registration_id
  }
  if (page.next_after !== null && (typeof page.next_after !== 'string' || page.results.length !== 100 || page.next_after !== previous)) throw new Error('Invalid roster cursor')
  // Explicit projection keeps private fields out of UI state.
  return { results: page.results.map(({ registration_id, student_id, student_name, semester, status, created_at }) =>
    ({ registration_id, student_id, student_name, semester, status, created_at })), next_after: page.next_after, names_unavailable: page.names_unavailable }
}


const registrationPath = (topicId: string, registrationId: string) =>
  `/registrations/api/v1/topics/${encodeURIComponent(topicId)}/registrations/${encodeURIComponent(registrationId)}/`

export async function cancelTopicRegistration(topicId: string, registrationId: string, signal: AbortSignal): Promise<void> {
  const response = await apiClient.delete(registrationPath(topicId, registrationId), { signal })
  if (response.status !== 204) throw new Error('Invalid cancellation response')
}

export async function getTopicRegistrationState(topicId: string, registrationId: string, signal: AbortSignal): Promise<number | null> {
  const { data } = await apiClient.get<unknown>(registrationPath(topicId, registrationId), { signal })
  if (!data || typeof data !== 'object') throw new Error('Invalid registration state')
  const row = data as Record<string, unknown>
  if (row.topic_id !== topicId || row.registration_id !== registrationId ||
      !(row.status === null || Number.isInteger(row.status))) throw new Error('Invalid registration state')
  return row.status as number | null
}

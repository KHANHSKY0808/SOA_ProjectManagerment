import { apiClient } from '../../services/api-client'

export interface Registration {
  registration_id: string
  topic_id: string | null
  semester: string | null
  status: number | null
  created_at: string | null
  updated_at: string | null
  point: string | null
}
export interface AvailableTopic {
  topic_id: string; name: string; major_id: string; status: 2
  req_GPA: number; studentQuota: number; registered_count: number; eligible: boolean
  ineligibility_reason: 'gpa_requirement_not_met' | 'topic_quota_full' | null
}
export interface TopicPage { results: AvailableTopic[]; next_after: string | null }
export interface RegisterInput { topic_id: string; semester?: string }

const base = '/registrations/api/v1/'
const records = base + 'registrations/'
const id = (value: unknown): value is string => typeof value === 'string' && !!value.trim() && value.length <= 255
const nullableString = (value: unknown): value is string | null => value === null || typeof value === 'string'
const timestamp = (value: unknown): value is string | null => value === null || (typeof value === 'string' &&
  /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value)))
const point = (value: unknown): value is string | null => value === null ||
  (typeof value === 'string' && /^(?:\d|10)\.\d{2}$/.test(value) && Number(value) <= 10)
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid registration response')
  return value as Record<string, unknown>
}
function registration(value: unknown): Registration {
  const row = object(value)
  if (!id(row.registration_id) || !(row.topic_id === null || id(row.topic_id)) || !nullableString(row.semester) ||
      !(row.status === null || (typeof row.status === 'number' && Number.isInteger(row.status))) ||
      !timestamp(row.created_at) || !timestamp(row.updated_at) || !point(row.point)) throw new Error('Invalid registration record')
  return { registration_id: row.registration_id, topic_id: row.topic_id, semester: row.semester,
    status: row.status as number | null, created_at: row.created_at, updated_at: row.updated_at, point: row.point }
}

/** Unknown legacy statuses, including null, conservatively count as current. */
export const isCurrent = (row: Registration): boolean => row.status !== 0

export async function listRegistrations(signal: AbortSignal): Promise<Registration[]> {
  const { data } = await apiClient.get<unknown>(records, { signal })
  if (!Array.isArray(data)) throw new Error('Invalid registration history')
  const rows = data.map(registration)
  if (new Set(rows.map(row => row.registration_id)).size !== rows.length) throw new Error('Duplicate registration IDs')
  return rows
}

/** Read the published student-facing topic reference before offering cancellation. */
export async function getRegistrationTopicStatus(topicId: string, signal: AbortSignal): Promise<number | null> {
  const { data } = await apiClient.get<unknown>(`/topics/api/v1/registration-topics/${encodeURIComponent(topicId)}/`, { signal })
  const topic = object(data)
  if (topic.topic_id !== topicId || !(topic.status === null ||
      (typeof topic.status === 'number' && Number.isInteger(topic.status)))) throw new Error('Invalid topic status')
  return topic.status as number | null
}

export async function listAvailableTopics(after: string, signal: AbortSignal): Promise<TopicPage> {
  const { data } = await apiClient.get<unknown>(base + 'available-topics/' + (after ? `?after=${encodeURIComponent(after)}` : ''), { signal })
  const page = object(data)
  if (!Array.isArray(page.results) || page.results.length > 100 || !(page.next_after === null || id(page.next_after))) {
    throw new Error('Invalid available topic page')
  }
  let previous = after
  const results: AvailableTopic[] = page.results.map(value => {
    const row = object(value)
    if (!id(row.topic_id) || row.topic_id <= previous || typeof row.name !== 'string' || !id(row.major_id) || row.status !== 2) {
      throw new Error('Invalid available topic')
    }
    previous = row.topic_id
    if (typeof row.req_GPA !== 'number' || !Number.isFinite(row.req_GPA) || row.req_GPA < 0 || row.req_GPA > 4 ||
        typeof row.studentQuota !== 'number' || !Number.isSafeInteger(row.studentQuota) || row.studentQuota < 1 || row.studentQuota > 2147483647 ||
        typeof row.registered_count !== 'number' || !Number.isSafeInteger(row.registered_count) || row.registered_count < 0 ||
        typeof row.eligible !== 'boolean' || ![null, 'gpa_requirement_not_met', 'topic_quota_full'].includes(row.ineligibility_reason as string | null) ||
        row.eligible !== (row.ineligibility_reason === null) || (row.eligible && row.registered_count >= row.studentQuota)) {
      throw new Error('Invalid topic eligibility')
    }
    return { topic_id: row.topic_id, name: row.name, major_id: row.major_id, status: 2,
      req_GPA: row.req_GPA, studentQuota: row.studentQuota, registered_count: row.registered_count,
      eligible: row.eligible, ineligibility_reason: row.ineligibility_reason as AvailableTopic['ineligibility_reason'] }
  })
  const cursor = page.next_after as string | null
  // The backend cursor belongs to the source page before faculty filtering.
  if (cursor !== null && (cursor <= after || cursor < previous)) throw new Error('Invalid topic cursor')
  return { results, next_after: cursor }
}

export async function registerTopic(input: RegisterInput, signal: AbortSignal): Promise<Registration> {
  const body: RegisterInput = { topic_id: input.topic_id }
  if (input.semester !== undefined) body.semester = input.semester
  const { data, status } = await apiClient.post<unknown>(records, body, { signal })
  const row = registration(data)
  if (![200, 201].includes(status) || row.topic_id !== input.topic_id || row.semester !== (input.semester ?? null) || !isCurrent(row)) {
    throw new Error('Invalid registration result')
  }
  return row
}

export async function cancelRegistration(registrationId: string, signal: AbortSignal): Promise<void> {
  const { status } = await apiClient.delete(`${records}${encodeURIComponent(registrationId)}/`, { signal })
  if (status !== 204) throw new Error('Invalid cancellation result')
}

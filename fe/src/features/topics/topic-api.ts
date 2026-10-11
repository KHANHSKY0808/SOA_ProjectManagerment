import { apiClient } from '../../services/api-client'

export interface Topic {
  topic_id: string
  name: string
  description: string | null
  major_name: string | null
  // This spelling is part of the published topic-service response contract.
  avisor_name: string | null
}
export type TopicStatus = 0 | 1 | 2
export const topicStatusLabels: Record<TopicStatus, string> = {
  0: 'Chờ duyệt', 1: 'Đã duyệt', 2: 'Mở đăng ký',
}
export function topicStatusLabel(status: number | null) {
  return status === 0 || status === 1 || status === 2 ? topicStatusLabels[status] : 'Chưa xác định'
}
export interface CreateTopic {
  status?: TopicStatus
  topic_id: string
  name: string
  description: string
  major_id: string
  advisor_id: string
}

export interface TopicDetail extends Topic {
  file_url: string | null
  status: number | null
  created_at: string | null
  updated_at: string | null
  updated_by: string | null
  major_id?: string
  advisor_id?: string | null
}
export type TopicUpdate = Partial<Pick<CreateTopic, 'name' | 'description' | 'major_id' | 'advisor_id' | 'status'>>

const path = '/topics/api/v1/topics/'
function topic(value: unknown): Topic {
  if (!value || typeof value !== 'object') throw new Error('Invalid topic response')
  const row = value as Record<string, unknown>
  if (typeof row.topic_id !== 'string' || !row.topic_id || typeof row.name !== 'string' ||
      !['description', 'major_name', 'avisor_name'].every(key => row[key] === null || typeof row[key] === 'string')) {
    throw new Error('Invalid topic response')
  }
  return row as unknown as Topic
}
export async function listTopics(signal: AbortSignal): Promise<Topic[]> {
  const { data } = await apiClient.get<unknown>(path, { signal })
  if (!Array.isArray(data)) throw new Error('Invalid topic list response')
  return data.map(topic)
}
export async function createTopic(input: CreateTopic, signal: AbortSignal): Promise<void> {
  await apiClient.post(path, input, { signal })
}
export async function getTopic(id: string, signal: AbortSignal): Promise<Topic> {
  const { data } = await apiClient.get<unknown>(`${path}${encodeURIComponent(id)}/`, { signal })
  const row = topic(data)
  if (row.topic_id !== id) throw new Error('Invalid topic identity')
  return row
}

export async function getTopicDetail(id: string, signal: AbortSignal): Promise<TopicDetail> {
  const row = await getTopic(id, signal) as TopicDetail
  if (!['file_url', 'created_at', 'updated_at', 'updated_by'].every(key => {
    const value = row[key as keyof TopicDetail]
    return value === null || typeof value === 'string'
  }) || !(row.status === null || Number.isInteger(row.status))) throw new Error('Invalid topic detail')
  return row
}

export async function updateTopic(id: string, input: TopicUpdate, signal: AbortSignal): Promise<void> {
  await apiClient.patch(`${path}${encodeURIComponent(id)}/`, input, { signal })
}

export async function deleteTopic(id: string, signal: AbortSignal): Promise<void> {
  await apiClient.delete(`${path}${encodeURIComponent(id)}/`, { signal })
}

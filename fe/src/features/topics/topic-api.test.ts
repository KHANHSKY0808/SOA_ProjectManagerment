import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { createTopic, deleteTopic, getTopic, getTopicDetail, listTopics, updateTopic } from './topic-api'

const base = '/topics/api/v1/topics/'
const row = { req_GPA: 0, studentQuota: 1, status: null, topic_id: 'guid-1', name: 'SOA', description: null, major_name: null, avisor_name: 'An' }
const detail = { ...row, major_id: '2', advisor_id: 'GV1', file_url: null, status: 0,
  created_at: null, updated_at: null, updated_by: null }
let mock: MockAdapter
beforeEach(() => { mock = new MockAdapter(apiClient, { onNoMatch: 'throwException' }); setAccessToken('test-token') })
afterEach(() => { mock.restore(); setAccessToken(null) })
describe('Topic Gateway API', () => {
  it.each([{ req_GPA: undefined }, { req_GPA: 5 }, { req_GPA: '3' }, { studentQuota: 0 }, { studentQuota: 1.5 }])('rejects invalid limits %#', async override => {
    mock.onGet(base).reply(200, [{ ...row, ...override }])
    await expect(listTopics(new AbortController().signal)).rejects.toThrow()
  })
  it('loads published names and forwards the JWT and abort signal', async () => {
    mock.onGet(base).reply(200, [row])
    const signal = new AbortController().signal
    expect(await listTopics(signal)).toEqual([row])
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer test-token')
    expect(mock.history.get[0].signal).toBe(signal)
  })
  it('posts only the provided create DTO', async () => {
    const input = { req_GPA: 0, studentQuota: 1, topic_id: 'guid-1', name: 'SOA', description: '', advisor_id: 'GV1', major_id: '2' }
    mock.onPost(base).reply(201, row)
    await createTopic(input, new AbortController().signal)
    expect(JSON.parse(mock.history.post[0].data)).toEqual(input)
    expect(mock.history.post).toHaveLength(1)
  })
  it('encodes the topic ID when checking creation', async () => {
    mock.onGet(`${base}guid%201/`).reply(200, { ...row, topic_id: 'guid 1' })
    expect((await getTopic('guid 1', new AbortController().signal)).topic_id).toBe('guid 1')
  })
  it.each([{}, [null], [{ ...row, status: undefined }], [{ ...row, status: true }], [{ ...row, major_name: 1 }], [{ ...row, topic_id: '' }]])('rejects malformed list responses %#', async (data) => {
    mock.onGet(base).reply(200, data)
    await expect(listTopics(new AbortController().signal)).rejects.toThrow()
  })
  it('rejects a mismatched detail identity', async () => {
    mock.onGet(`${base}different/`).reply(200, row)
    await expect(getTopic('different', new AbortController().signal)).rejects.toThrow('Invalid topic identity')
  })
  it('loads full detail including nullable business metadata and management IDs', async () => {
    mock.onGet(`${base}guid-1/`).reply(200, detail)
    const signal = new AbortController().signal
    expect(await getTopicDetail('guid-1', signal)).toEqual(detail)
    expect(mock.history.get[0].signal).toBe(signal)
  })
  it.each([
    { ...detail, status: '1' }, { ...detail, status: 1.2 },
    { ...detail, created_at: {} }, { ...detail, file_url: undefined },
  ])('rejects malformed detail metadata %#', async data => {
    mock.onGet(`${base}guid-1/`).reply(200, data)
    await expect(getTopicDetail('guid-1', new AbortController().signal)).rejects.toThrow()
  })
  it('encodes mutation IDs, sends only the PATCH DTO and forwards JWT/signal', async () => {
    const signal = new AbortController().signal
    mock.onPatch(`${base}DT%20%23%3F/`).reply(200, detail)
    mock.onDelete(`${base}DT%20%23%3F/`).reply(204)
    await updateTopic('DT #?', { name: 'New name' }, signal)
    await deleteTopic('DT #?', signal)
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ name: 'New name' })
    for (const request of [...mock.history.patch, ...mock.history.delete]) {
      expect(request.signal).toBe(signal)
      expect(request.headers?.Authorization).toBe('Bearer test-token')
    }
    expect(mock.history.put).toHaveLength(0)
    expect(mock.history.post).toHaveLength(0)
  })
  it.each([403, 404, 409, 503])('preserves safe mutation HTTP %s errors without automatic retries', async status => {
    mock.onPatch(`${base}guid-1/`).reply(status, { detail: 'private server data' })
    mock.onDelete(`${base}guid-1/`).reply(status, { detail: 'private server data' })
    const signal = new AbortController().signal
    await expect(updateTopic('guid-1', { description: '' }, signal)).rejects.toMatchObject({ kind: 'http', status })
    await expect(deleteTopic('guid-1', signal)).rejects.toMatchObject({ kind: 'http', status })
    expect(mock.history.patch).toHaveLength(1)
    expect(mock.history.delete).toHaveLength(1)
  })
  it('does not send cancelled requests', async () => {
    const controller = new AbortController(); controller.abort()
    await expect(listTopics(controller.signal)).rejects.toMatchObject({ kind: 'cancelled' })
    await expect(updateTopic('guid-1', { name: 'New' }, controller.signal)).rejects.toMatchObject({ kind: 'cancelled' })
    await expect(deleteTopic('guid-1', controller.signal)).rejects.toMatchObject({ kind: 'cancelled' })
    expect(mock.history.get).toHaveLength(0)
    expect(mock.history.patch).toHaveLength(0)
    expect(mock.history.delete).toHaveLength(0)
  })
})

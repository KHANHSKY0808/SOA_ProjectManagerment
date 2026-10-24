import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { cancelRegistration, getRegistrationTopicStatus, isCurrent, listAvailableTopics, listRegistrations, registerTopic } from './registration-api'

const base = '/registrations/api/v1/'
const row = { registration_id: 'R1', topic_id: 'T1', semester: null, status: 1,
  created_at: '2026-10-11T03:00:00Z', updated_at: null, point: null }
const topic = { topic_id: 'T1', major_id: 'M1', name: 'SOA', req_GPA: 0, studentQuota: 1, registered_count: 0, eligible: true, ineligibility_reason: null, status: 2 }
const signal = new AbortController().signal
let mock: MockAdapter
beforeEach(() => { mock = new MockAdapter(apiClient, { onNoMatch: 'throwException' }); setAccessToken('student-token') })
afterEach(() => { mock.restore(); setAccessToken(null) })

describe('Student registration Gateway contract', () => {
  it.each([
    { req_GPA: undefined }, { req_GPA: 5 }, { studentQuota: 0 }, { studentQuota: 1.5 },
    { registered_count: -1 }, { eligible: undefined }, { eligible: true, ineligibility_reason: 'topic_quota_full' },
    { eligible: true, registered_count: 1 },
  ])('rejects invalid or missing eligibility fields %#', async override => {
    mock.onGet(base + 'available-topics/').reply(200, { results: [{ ...topic, ...override }], next_after: null })
    await expect(listAvailableTopics('', signal)).rejects.toThrow()
  })
  it('reads topic status through the student reference endpoint with JWT and signal', async () => {
    mock.onGet('/topics/api/v1/registration-topics/T%20%23%3F/').reply(200, { topic_id: 'T #?', status: 3 })
    expect(await getRegistrationTopicStatus('T #?', signal)).toBe(3)
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer student-token')
    expect(mock.history.get[0].signal).toBe(signal)
  })
  it.each([{ topic_id: 'T2', status: 3 }, { topic_id: 'T1' }, { topic_id: 'T1', status: '3' }])('rejects invalid topic status %#', async data => {
    mock.onGet('/topics/api/v1/registration-topics/T1/').reply(200, data)
    await expect(getRegistrationTopicStatus('T1', signal)).rejects.toThrow()
  })
  it('loads own history and strips unrequested fields, forwarding JWT and signal', async () => {
    mock.onGet(base + 'registrations/').reply(200, [{ ...row, student_id: 'private', notes: 'private' }])
    expect(await listRegistrations(signal)).toEqual([row])
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer student-token')
    expect(mock.history.get[0].signal).toBe(signal)
  })
  it('accepts a graded registration and rejects malformed points', async () => {
    mock.onGet(base + 'registrations/').reply(200, [{ ...row, point: '8.50' }])
    expect((await listRegistrations(signal))[0].point).toBe('8.50')
    for (const point of ['11.00', '-1.00', '8.123', 8.5, 'NaN']) {
      mock.onGet(base + 'registrations/').reply(200, [{ ...row, point }])
      await expect(listRegistrations(signal)).rejects.toThrow()
    }
  })
  it.each([null, {}, [null], [{ ...row, status: '1' }], [{ ...row, created_at: 'invalid' }], [row, row],
    [{ ...row, updated_at: undefined }], [{ ...row, registration_id: '' }]])('rejects invalid history %#', async data => {
    mock.onGet(base + 'registrations/').reply(200, data)
    await expect(listRegistrations(signal)).rejects.toThrow()
  })
  it('accepts legacy nullable metadata while treating nonzero/null status as current', async () => {
    mock.onGet(base + 'registrations/').reply(200, [{ ...row, status: null, topic_id: null, created_at: null }])
    expect(isCurrent((await listRegistrations(signal))[0])).toBe(true)
    expect(isCurrent({ ...row, status: 2 })).toBe(true)
    expect(isCurrent({ ...row, status: 0 })).toBe(false)
  })
  it('accepts filtered empty pages with a progressing cursor and encodes the next request', async () => {
    mock.onGet(base + 'available-topics/').reply(200, { results: [], next_after: 'T #?' })
    expect(await listAvailableTopics('', signal)).toEqual({ results: [], next_after: 'T #?' })
    mock.onGet(base + 'available-topics/?after=T%20%23%3F').reply(200, { results: [topic], next_after: null })
    expect((await listAvailableTopics('T #?', signal)).results).toEqual([topic])
  })
  it.each([
    { results: [topic], next_after: 'T0' }, { results: [], next_after: '' },
    { results: [{ ...topic, status: 0 }], next_after: null }, { results: [{ ...topic, status: 1 }], next_after: null }, { results: [topic, topic], next_after: null },
    { results: [{ ...topic, major_id: null }], next_after: null }, { results: [], next_after: 'T0' },
  ])('rejects malformed/non-progressing pages %#', async data => {
    mock.onGet(base + 'available-topics/?after=T0').reply(200, data)
    await expect(listAvailableTopics('T0', signal)).rejects.toThrow()
  })
  it.each([200, 201])('registers with HTTP %s and only published fields', async status => {
    mock.onPost(base + 'registrations/').reply(status, { ...row, semester: '2026-1' })
    const input = { topic_id: 'T1', semester: '2026-1', student_id: 'spoofed' }
    expect(await registerTopic(input, signal)).toEqual({ ...row, semester: '2026-1' })
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ topic_id: 'T1', semester: '2026-1' })
    expect(mock.history.post[0].signal).toBe(signal)
  })
  it.each([{ ...row, topic_id: 'different' }, { ...row, status: 0 }, { ...row, semester: 'wrong' }, {}])(
    'rejects ambiguous successful mutation data %#', async data => {
      mock.onPost(base + 'registrations/').reply(201, data)
      await expect(registerTopic({ topic_id: 'T1' }, signal)).rejects.toThrow()
    })
  it('encodes cancellation ID, passes JWT/signal and requires 204', async () => {
    mock.onDelete(base + 'registrations/R%20%23%3F/').reply(204)
    await cancelRegistration('R #?', signal)
    expect(mock.history.delete[0].headers?.Authorization).toBe('Bearer student-token')
    expect(mock.history.delete[0].signal).toBe(signal)
    mock.onDelete(base + 'registrations/R1/').reply(200)
    await expect(cancelRegistration('R1', signal)).rejects.toThrow()
  })
  it.each([400, 401, 403, 404, 409, 503])('retains HTTP %s errors without retry', async status => {
    mock.onPost(base + 'registrations/').reply(status, { code: 'test', detail: 'private' })
    await expect(registerTopic({ topic_id: 'T1' }, signal)).rejects.toMatchObject({ status, details: { code: 'test', detail: 'private' } })
    expect(mock.history.post).toHaveLength(1)
  })
})

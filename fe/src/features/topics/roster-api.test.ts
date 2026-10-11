import MockAdapter from 'axios-mock-adapter'
import { beforeEach, afterEach, expect, it } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { getTopicRoster, cancelTopicRegistration, getTopicRegistrationState } from './roster-api'
const url = '/registrations/api/v1/topics/T%20%23/registrations/'
const row = { registration_id: 'R1', student_id: 'S1', student_name: null, semester: null, status: 1, created_at: null }
const page = { results: [row], next_after: null, names_unavailable: true }
let mock: MockAdapter
beforeEach(() => { mock = new MockAdapter(apiClient); setAccessToken('test-token') })
afterEach(() => { mock.restore(); setAccessToken(null) })
it('encodes IDs/cursor, forwards bearer/signal and strips private fields', async () => {
  const signal = new AbortController().signal
  mock.onGet(url + '?after=R%20%23').reply(200, { ...page, results: [{ ...row, email: 'private' }] })
  expect(await getTopicRoster('T #', 'R #', signal)).toEqual(page)
  expect(mock.history.get[0].signal).toBe(signal)
  expect(mock.history.get[0].headers?.Authorization).toBe('Bearer test-token')
})
it.each([null, {}, { ...page, results: [null] }, { ...page, results: [row, row] },
  { ...page, results: [{ ...row, created_at: 'invalid' }] }, { ...page, results: [{ ...row, status: 0 }] }, { ...page, results: [{ ...row, student_name: 4 }] },
  { ...page, names_unavailable: 'false' }, { ...page, next_after: 'R1' }])('rejects invalid roster %#', async data => {
  mock.onGet(url).reply(200, data)
  await expect(getTopicRoster('T #', '', new AbortController().signal)).rejects.toThrow()
})
it('preserves HTTP failure without retrying and honours aborted requests', async () => {
  mock.onGet(url).reply(503, {})
  await expect(getTopicRoster('T #', '', new AbortController().signal)).rejects.toMatchObject({ status: 503 })
  expect(mock.history.get).toHaveLength(1)
  const controller = new AbortController(); controller.abort()
  await expect(getTopicRoster('T #', '', controller.signal)).rejects.toMatchObject({ kind: 'cancelled' })
  expect(mock.history.get).toHaveLength(1)
})

it('encodes cancellation IDs and sends authenticated DELETE with no body', async () => {
  const path = url + 'R%20%23/'
  const signal = new AbortController().signal
  mock.onDelete(path).reply(204)
  await cancelTopicRegistration('T #', 'R #', signal)
  expect(mock.history.delete[0].signal).toBe(signal)
  expect(mock.history.delete[0].headers?.Authorization).toBe('Bearer test-token')
  expect(mock.history.delete[0].data).toBeUndefined()
  mock.onDelete(path).reply(200)
  await expect(cancelTopicRegistration('T #', 'R #', signal)).rejects.toThrow()
})
it.each([0, 1, null, 2])('reads exact registration state %s for reconciliation', async status => {
  mock.onGet(url + 'R1/').reply(200, { registration_id: 'R1', topic_id: 'T #', status })
  expect(await getTopicRegistrationState('T #', 'R1', new AbortController().signal)).toBe(status)
})
it.each([{}, { registration_id: 'R1', topic_id: 'wrong', status: 0 },
  { registration_id: 'wrong', topic_id: 'T #', status: 0 }, { registration_id: 'R1', topic_id: 'T #', status: '0' }])('rejects invalid cancellation reconciliation %#', async data => {
  mock.onGet(url + 'R1/').reply(200, data)
  await expect(getTopicRegistrationState('T #', 'R1', new AbortController().signal)).rejects.toThrow()
})
it('never retries DELETE and honours cancellation', async () => {
  mock.onDelete(url + 'R1/').timeout()
  await expect(cancelTopicRegistration('T #', 'R1', new AbortController().signal)).rejects.toMatchObject({ kind: 'timeout' })
  expect(mock.history.delete).toHaveLength(1)
  const controller = new AbortController(); controller.abort()
  await expect(cancelTopicRegistration('T #', 'R1', controller.signal)).rejects.toMatchObject({ kind: 'cancelled' })
  expect(mock.history.delete).toHaveLength(1)
})

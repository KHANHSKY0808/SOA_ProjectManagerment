import MockAdapter from 'axios-mock-adapter'
import { beforeEach, afterEach, expect, it } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { getTopicRoster } from './roster-api'
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

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { AuthContext } from '../auth/auth-context'
import type { Role } from '../auth/auth-types'
import type { RegisteredStudent } from '../topics/roster-api'
import { AdminRegistrationPage } from './AdminRegistrationPage'

const topicsUrl = '/topics/api/v1/topics/'
const rosterUrl = (topic = 'T1') => `/registrations/api/v1/topics/${topic}/registrations/`
const topic = { topic_id: 'T1', name: 'Quản lý đồ án', status: 3, req_GPA: 2.5, studentQuota: 5,
  description: 'SOA', major_name: 'Công nghệ thông tin', avisor_name: 'Trần Bình',
  file_url: null, created_at: null, updated_at: null, updated_by: null }
const other = { ...topic, topic_id: 'T2', name: 'Thư viện', status: 2 }
const student: RegisteredStudent = { registration_id: 'R001', student_id: 'SV001', student_name: 'Nguyễn An', semester: '2026-1',
  status: 1, created_at: '2026-10-24T01:00:00Z', point: null as string | null }
const page = (results = [student], next_after: string | null = null, names_unavailable = false) => ({ results, next_after, names_unavailable })
const logout = vi.fn()
let mock: MockAdapter
beforeEach(() => {
  logout.mockReset(); setAccessToken('test-token')
  mock = new MockAdapter(apiClient, { onNoMatch: 'throwException' })
  mock.onGet(topicsUrl).reply(200, [topic, other])
  mock.onGet(topicsUrl + 'T1/').reply(200, topic)
  mock.onGet(topicsUrl + 'T2/').reply(200, other)
  mock.onGet(rosterUrl()).reply(200, page())
  mock.onGet(rosterUrl('T2')).reply(200, page([{ ...student, registration_id: 'R002', student_id: 'SV002', student_name: 'Lê Lan' }]))
})
afterEach(() => { mock.restore(); setAccessToken(null) })
function renderPage(role: Role = 1) {
  return render(<AuthContext.Provider value={{ user: { user_id: 'admin', first_name: null, last_name: null, role },
    logout, login: vi.fn(), status: 'ready', restoreError: '', retryRestore: vi.fn() }}><AdminRegistrationPage /></AuthContext.Provider>)
}
async function ready() {
  renderPage()
  await screen.findByRole('button', { name: 'Chấm điểm SV001' })
}
function grade(value = '8.5') {
  fireEvent.click(screen.getByRole('button', { name: 'Chấm điểm SV001' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Điểm (0–10)' }), { target: { value } })
  fireEvent.submit(screen.getByRole('form', { name: 'Chấm điểm đăng ký' }))
}

it('shows topic information and all registration fields, switching to the selected topic', async () => {
  await ready()
  expect(screen.getByRole('combobox', { name: 'Đề tài' })).toHaveValue('T1')
  expect(screen.getByRole('option', { name: 'T2 — Thư viện' })).toBeVisible()
  for (const text of ['Trần Bình', 'Công nghệ thông tin', 'Đóng đăng ký', '2.5', '5']) expect(screen.getByText(text)).toBeVisible()
  const table = screen.getByRole('table', { name: 'Danh sách sinh viên đăng ký' })
  expect(within(table).getAllByRole('columnheader').map(cell => cell.textContent)).toEqual([
    'Mã đăng ký', 'Mã sinh viên', 'Họ tên', 'Học kỳ', 'Ngày đăng ký', 'Trạng thái đăng ký', 'Điểm', 'Thao tác',
  ])
  for (const text of ['R001', 'SV001', 'Nguyễn An', '2026-1', 'Đang đăng ký', 'Chưa chấm']) expect(within(table).getByText(text)).toBeVisible()
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'T2' } })
  expect(screen.queryByText('Nguyễn An')).not.toBeInTheDocument()
  expect(await screen.findByText('Lê Lan')).toBeVisible()
  expect(await screen.findByText('Chỉ có thể chấm điểm khi đề tài đã đóng đăng ký.')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Chấm điểm SV002' })).not.toBeInTheDocument()
  expect(mock.history.get.find(request => request.url === rosterUrl())?.headers?.Authorization).toBe('Bearer test-token')
})

it('ignores late responses from a previously selected topic', async () => {
  let complete!: (result: [number, unknown]) => void
  let completeDetail!: (result: [number, unknown]) => void
  mock.onGet(rosterUrl()).reply(() => new Promise(resolve => { complete = resolve }))
  mock.onGet(topicsUrl + 'T1/').reply(() => new Promise(resolve => { completeDetail = resolve }))
  renderPage()
  await screen.findByRole('combobox')
  await waitFor(() => expect(mock.history.get.some(request => request.url === rosterUrl())).toBe(true))
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'T2' } })
  await screen.findByText('Lê Lan')
  await act(async () => { complete([200, page()]); completeDetail([200, topic]) })
  expect(screen.queryByText('Nguyễn An')).not.toBeInTheDocument()
  expect(screen.queryByText('Đóng đăng ký')).not.toBeInTheDocument()
  expect(screen.getByRole('combobox')).toHaveValue('T2')
})

it('confirms cancellation and removes only the cancelled row', async () => {
  mock.onDelete(rosterUrl() + 'R001/').reply(204)
  await ready()
  fireEvent.click(screen.getByRole('button', { name: 'Hủy đăng ký SV001' }))
  expect(mock.history.delete).toHaveLength(0)
  expect(screen.getByRole('combobox')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận hủy đăng ký' }))
  await screen.findByText('Đã hủy đăng ký sinh viên khỏi đề tài.')
  expect(screen.queryByText('Nguyễn An')).not.toBeInTheDocument()
  expect(screen.getByRole('combobox')).toBeEnabled()
  expect(mock.history.delete).toHaveLength(1)
})

it('reconciles an uncertain cancellation before allowing topic changes', async () => {
  mock.onDelete(rosterUrl() + 'R001/').timeout()
  await ready()
  fireEvent.click(screen.getByRole('button', { name: 'Hủy đăng ký SV001' }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận hủy đăng ký' }))
  const check = await screen.findByRole('button', { name: 'Kiểm tra kết quả hủy' })
  expect(screen.getByRole('combobox')).toBeDisabled()
  mock.onGet(rosterUrl() + 'R001/').reply(200, { ...student, topic_id: 'T1', status: 0 })
  fireEvent.click(check)
  await screen.findByText('Đã xác nhận hủy đăng ký.')
  expect(screen.getByRole('combobox')).toBeEnabled()
  expect(mock.history.delete).toHaveLength(1)
})

it.each(['success', 'timeout'] as const)('saves points and reconciles without duplicate writes (%s)', async result => {
  if (result === 'timeout') mock.onPut(rosterUrl() + 'R001/point/').timeout()
  else mock.onPut(rosterUrl() + 'R001/point/').reply(200, { registration_id: 'R001', topic_id: 'T1', point: '8.50', updated_at: '2026-10-24T01:00:00Z' })
  await ready(); grade()
  if (result === 'timeout') {
    const check = await screen.findByRole('button', { name: 'Kiểm tra điểm' })
    expect(screen.getByRole('combobox')).toBeDisabled()
    mock.onGet(rosterUrl() + 'R001/').reply(200, { ...student, topic_id: 'T1', point: '8.50' })
    fireEvent.click(check)
  }
  await screen.findByText('Đã lưu điểm đăng ký.')
  expect(screen.getByText('8.50')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Chấm điểm SV001' })).toHaveTextContent('Sửa điểm')
  expect(screen.getByRole('combobox')).toBeEnabled()
  expect(mock.history.put).toHaveLength(1)
  expect(JSON.parse(mock.history.put[0].data)).toEqual({ point: '8.5' })
})

it.each(['-1', '10.1', '8.555'])('rejects invalid point %s before sending', async value => {
  await ready(); grade(value)
  expect(await screen.findByText('Điểm phải từ 0 đến 10, tối đa 2 chữ số thập phân.')).toBeVisible()
  expect(mock.history.put).toHaveLength(0)
  expect(screen.getByRole('combobox')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Quay lại' }))
  expect(screen.getByRole('combobox')).toBeEnabled()
})

it('refreshes topic state after a concurrent reopening blocks grading', async () => {
  mock.onPut(rosterUrl() + 'R001/point/').reply(() => {
    mock.onGet(topicsUrl + 'T1/').reply(200, { ...topic, status: 2 })
    return [409, { code: 'topic_not_closed' }]
  })
  await ready(); grade()
  await screen.findByText('Mở đăng ký')
  expect(screen.queryByRole('button', { name: 'Chấm điểm SV001' })).not.toBeInTheDocument()
  expect(mock.history.put).toHaveLength(1)
})

it.each([401, 403, 503])('handles list HTTP %s without exposing private errors', async status => {
  mock.onGet(topicsUrl).reply(status, { detail: 'private details' })
  renderPage()
  if (status === 401) await waitFor(() => expect(logout).toHaveBeenCalledOnce())
  else {
    await screen.findByText('Không thể tải danh sách đề tài. Vui lòng thử lại.')
    mock.onGet(topicsUrl).reply(200, [])
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại đề tài' }))
    await screen.findByText('Chưa có đề tài để quản lý đăng ký.')
  }
  expect(screen.queryByText('private details')).not.toBeInTheDocument()
})

it('handles missing names and empty rosters', async () => {
  mock.onGet(rosterUrl()).reply(200, page([{ ...student, student_name: null, student_id: null, semester: null, created_at: null, status: null }], null, true))
  renderPage()
  await screen.findByText('Chưa có tên')
  expect(screen.getByText(/Chưa tra cứu được đầy đủ họ tên/)).toBeVisible()
  expect(screen.getByText('Cần kiểm tra')).toBeVisible()
  mock.onGet(rosterUrl('T2')).reply(200, page([]))
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'T2' } })
  await screen.findByText('Chưa có sinh viên đăng ký đề tài này.')
})

it('retries detail and roster failures and reloads from the first page', async () => {
  mock.onGet(topicsUrl + 'T1/').reply(503)
  mock.onGet(rosterUrl()).reply(503)
  renderPage()
  await screen.findByText('Không thể tải thông tin đề tài. Vui lòng thử lại.')
  await screen.findByText('Không thể tải danh sách sinh viên đăng ký. Vui lòng thử lại.')
  mock.onGet(topicsUrl + 'T1/').reply(200, topic)
  mock.onGet(rosterUrl()).reply(200, page())
  fireEvent.click(screen.getByRole('button', { name: 'Tải lại thông tin đề tài' }))
  fireEvent.click(screen.getByRole('button', { name: 'Tải lại danh sách sinh viên' }))
  await screen.findByRole('button', { name: 'Chấm điểm SV001' })
  mock.onGet(rosterUrl()).reply(200, page([]))
  fireEvent.click(screen.getByRole('button', { name: 'Tải lại' }))
  await screen.findByText('Chưa có sinh viên đăng ký đề tài này.')
})

it('loads additional registration pages without losing previous rows', async () => {
  const students = Array.from({ length: 100 }, (_, index) => ({ ...student, registration_id: `R${String(index).padStart(3, '0')}` }))
  mock.onGet(rosterUrl()).reply(200, page(students, 'R099'))
  mock.onGet(rosterUrl() + '?after=R099').reply(200, page([{ ...student, registration_id: 'R100', student_name: 'Sinh viên tiếp' }]))
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: 'Xem thêm sinh viên' }))
  await screen.findByText('Sinh viên tiếp')
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(102)
  expect(screen.queryByRole('button', { name: 'Xem thêm sinh viên' })).not.toBeInTheDocument()
})

it.each([2, 3] as const)('does not call management APIs for role %s', async role => {
  renderPage(role)
  expect(screen.getByRole('alert')).toHaveTextContent('Bạn không có quyền quản lý đăng ký.')
  expect(mock.history.get).toHaveLength(0)
})

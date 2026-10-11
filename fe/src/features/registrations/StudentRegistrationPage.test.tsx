import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, setAccessToken } from '../../services/api-client'
import { AuthContext } from '../auth/auth-context'
import { StudentRegistrationPage } from './StudentRegistrationPage'

const base = '/registrations/api/v1/'
const records = base + 'registrations/'
const available = base + 'available-topics/'
const topics = [
  { topic_id: 'T1', name: 'Quản lý đồ án', major_id: 'M1', status: 1 },
  { topic_id: 'T2', name: 'Thư viện số', major_id: 'M2', status: 1 },
]
const record = { registration_id: 'R1', topic_id: 'T1', semester: null, status: 1,
  created_at: '2026-10-11T03:00:00Z', updated_at: '2026-10-11T03:00:00Z' }
const logout = vi.fn()
let mock: MockAdapter
beforeEach(() => {
  logout.mockReset(); setAccessToken('student-token')
  mock = new MockAdapter(apiClient, { onNoMatch: 'throwException' })
  mock.onGet(records).reply(200, [])
  mock.onGet(available).reply(200, { results: topics, next_after: null })
})
afterEach(() => { mock.restore(); setAccessToken(null) })
function renderPage() {
  return render(<AuthContext.Provider value={{ user: { user_id: 'SV1', first_name: 'An', last_name: null, role: 3 },
    logout, login: vi.fn(), status: 'ready', restoreError: '', retryRestore: vi.fn() }}><StudentRegistrationPage /></AuthContext.Provider>)
}
async function ready() {
  await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })
  await waitFor(() => expect(screen.queryByText('Đang tải đăng ký…')).not.toBeInTheDocument())
}
async function openRegister() {
  await ready()
  const opener = screen.getByRole('button', { name: 'Đăng ký T1' })
  opener.focus(); fireEvent.click(opener)
  return screen.getByRole('form', { name: 'Đăng ký đề tài' })
}

describe('Student registration workflow', () => {
  it('loads independent lists, shows eligible topics and searches only on submit', async () => {
    renderPage(); await ready()
    expect(screen.getByText(/Bạn chưa đăng ký đề tài/)).toBeVisible()
    const list = screen.getByRole('table', { name: 'Đề tài mở đăng ký' })
    const search = screen.getByRole('searchbox')
    fireEvent.change(search, { target: { value: ' THƯ VIỆN ' } })
    expect(within(list).getByText('T1')).toBeVisible()
    fireEvent.submit(screen.getByRole('search'))
    expect(within(list).queryByText('T1')).not.toBeInTheDocument()
    expect(within(list).getByText('T2')).toBeVisible()
    expect(mock.history.get.map(request => request.url).sort()).toEqual([available, records].sort())
  })

  it('registers after confirmation with optional semester and refreshes own history', async () => {
    mock.onPost(records).reply(config => {
      const row = { ...record, semester: '2026-1' }
      expect(JSON.parse(config.data)).toEqual({ topic_id: 'T1', semester: '2026-1' })
      mock.onGet(records).reply(200, [row])
      return [201, row]
    })
    renderPage(); const form = await openRegister()
    expect(mock.history.post).toHaveLength(0)
    expect(screen.getByLabelText('Học kỳ (không bắt buộc)')).toHaveFocus()
    fireEvent.change(screen.getByLabelText('Học kỳ (không bắt buộc)'), { target: { value: ' 2026-1 ' } })
    fireEvent.submit(form)
    expect(await screen.findByText('Đăng ký đề tài thành công.')).toBeVisible()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Đăng ký T2' })).toBeDisabled()
    expect(await screen.findByRole('button', { name: 'Hủy đăng ký T1' })).toBeEnabled()
    expect(mock.history.post[0].headers?.Authorization).toBe('Bearer student-token')
  })

  it('cancels with confirmation, keeps history and enables another registration', async () => {
    mock.onGet(records).reply(200, [record])
    mock.onDelete(records + 'R1/').reply(() => {
      mock.onGet(records).reply(200, [{ ...record, status: 0 }]); return [204]
    })
    renderPage(); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Hủy đăng ký T1' }))
    expect(mock.history.delete).toHaveLength(0)
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận hủy' }))
    expect(await screen.findByText('Đã hủy đăng ký đề tài.')).toBeVisible()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Đăng ký T2' })).toBeEnabled())
    expect(within(screen.getByRole('table', { name: 'Lịch sử đăng ký' })).getByText('Đã hủy')).toBeVisible()
    fireEvent.change(screen.getByRole('combobox', { name: 'Lọc lịch sử' }), { target: { value: 'active' } })
    expect(screen.getByText('Chưa có đăng ký trong danh sách này.')).toBeVisible()
    expect(mock.history.delete).toHaveLength(1)
  })

  it.each([1, 2, null])('blocks another registration for current legacy status %s', async status => {
    mock.onGet(records).reply(200, [{ ...record, status }])
    renderPage(); await ready()
    expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Hủy đăng ký T1' })).toBeEnabled()
    if (status !== 1) expect(screen.getAllByText('Cần kiểm tra trạng thái')).toHaveLength(2)
  })

  it('warns about legacy duplicates and allows owner cancellation without another registration', async () => {
    mock.onGet(records).reply(200, [record, { ...record, registration_id: 'R2', topic_id: 'T2' }])
    renderPage(); await ready()
    expect(screen.getByRole('alert')).toHaveTextContent('Có nhiều đăng ký hiện tại')
    expect(screen.getByRole('button', { name: 'Đăng ký T2' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Hủy đăng ký T2' })).toBeEnabled()
  })

  it('loads more after a filtered empty page and applies the existing search to new rows', async () => {
    mock.onGet(available).reply(200, { results: [], next_after: 'T0' })
    mock.onGet(available + '?after=T0').reply(200, { results: topics, next_after: null })
    renderPage(); await ready()
    expect(screen.getByText(/Trang này chưa có đề tài thuộc khoa/)).toBeVisible()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'thư viện' } })
    fireEvent.submit(screen.getByRole('search'))
    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm đề tài' }))
    expect(await screen.findByText('Thư viện số')).toBeVisible()
    expect(screen.queryByText('Quản lý đồ án')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Tải thêm đề tài' })).not.toBeInTheDocument()
  })

  it('preserves a loaded page and cursor after load-more failure, then retries that page', async () => {
    mock.onGet(available).reply(200, { results: [topics[0]], next_after: 'T1' })
    mock.onGet(available + '?after=T1').reply(503)
    renderPage(); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm đề tài' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Dịch vụ tạm thời')
    expect(screen.getByText('Quản lý đồ án')).toBeVisible()
    mock.onGet(available + '?after=T1').reply(200, { results: [topics[1]], next_after: null })
    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm đề tài' }))
    expect(await screen.findByText('Thư viện số')).toBeVisible()
    expect(within(screen.getByRole('table', { name: 'Đề tài mở đăng ký' })).getAllByRole('row')).toHaveLength(3)
  })

  it('keeps topic failure independent from an existing registration and cancellation', async () => {
    mock.onGet(available).reply(503)
    mock.onGet(records).reply(200, [record])
    renderPage()
    expect(await screen.findByRole('button', { name: 'Hủy đăng ký T1' })).toBeEnabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Dịch vụ tạm thời')
    expect(within(screen.getByRole('table', { name: 'Lịch sử đăng ký' })).getByText('T1')).toBeVisible()
  })

  it('disables writes when history fails even if topics load, and recovers after refresh', async () => {
    mock.onGet(records).reply(503)
    renderPage(); await ready()
    expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toBeDisabled()
    mock.onGet(records).reply(200, [])
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toBeEnabled())
  })

  it.each([
    [400, 'topic_closed', 'Đề tài đã đóng đăng ký.'],
    [400, 'faculty_mismatch', 'Đề tài không thuộc khoa của bạn.'],
    [400, 'invalid', 'Thông tin đăng ký không hợp lệ.'],
    [403, 'permission_denied', 'Bạn không có quyền hoặc hồ sơ sinh viên'],
    [404, 'not_found', 'Đề tài hoặc đăng ký không còn tồn tại.'],
  ])('shows safe Vietnamese feedback for HTTP %s / %s', async (status, code, text) => {
    mock.onPost(records).reply(status as number, { code, detail: 'private server detail' })
    renderPage(); const form = await openRegister(); fireEvent.submit(form)
    expect(await screen.findByRole('alert')).toHaveTextContent(text as string)
    expect(screen.queryByText('private server detail')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Xác nhận đăng ký' })).toBeEnabled()
    expect(mock.history.post).toHaveLength(1)
  })

  it.each(['network', 'timeout', 409, 503, 'malformed'] as const)('locks uncertain %s creation until explicit history reconciliation', async failure => {
    const handler = mock.onPost(records)
    if (failure === 'network') handler.networkError()
    else if (failure === 'timeout') handler.timeout()
    else if (failure === 'malformed') handler.reply(201, {})
    else handler.reply(failure)
    renderPage(); const form = await openRegister(); fireEvent.submit(form)
    const check = await screen.findByRole('button', { name: 'Kiểm tra kết quả' })
    expect(screen.getByLabelText('Học kỳ (không bắt buộc)')).toBeDisabled()
    fireEvent.submit(form)
    expect(mock.history.post).toHaveLength(1)
    mock.onGet(records).reply(200, [record])
    fireEvent.click(check)
    expect(await screen.findByText('Đã xác nhận đăng ký đề tài thành công.')).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đăng ký T2' })).toBeDisabled()
    expect(mock.history.post).toHaveLength(1)
  })

  it('keeps uncertain writes locked after failed checking, including closing the dialog', async () => {
    mock.onPost(records).timeout()
    renderPage(); const form = await openRegister(); fireEvent.submit(form)
    fireEvent.click(await screen.findByRole('button', { name: 'Đóng' }))
    await screen.findByRole('button', { name: 'Kiểm tra kết quả' })
    mock.onGet(records).reply(503)
    fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra kết quả' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Kiểm tra kết quả' })).toBeEnabled())
    expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toBeDisabled()
    expect(screen.getByRole('region', { name: 'Kiểm tra thao tác' })).toBeVisible()
    mock.onGet(records).reply(200, [])
    fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra kết quả' }))
    expect(await screen.findByText('Chưa có đăng ký hiện tại. Bạn có thể chọn đăng ký lại.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toBeEnabled()
    expect(mock.history.post).toHaveLength(1)
  })

  it.each([404, 503] as const)('reconciles cancellation HTTP %s before allowing another write', async status => {
    mock.onGet(records).reply(200, [record])
    mock.onDelete(records + 'R1/').reply(status)
    renderPage(); await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Hủy đăng ký T1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận hủy' }))
    const check = await screen.findByRole('button', { name: 'Kiểm tra kết quả' })
    mock.onGet(records).reply(200, [{ ...record, status: 0 }])
    fireEvent.click(check)
    expect(await screen.findByText('Đăng ký này không còn hiệu lực.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Đăng ký T2' })).toBeEnabled()
    expect(mock.history.delete).toHaveLength(1)
  })

  it('prevents double submit and closing a dialog while a mutation is pending', async () => {
    let complete!: (response: [number, unknown]) => void
    mock.onPost(records).reply(() => new Promise<[number, unknown]>(resolve => { complete = resolve }))
    renderPage(); const form = await openRegister()
    fireEvent.submit(form); fireEvent.submit(form)
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    expect(screen.getByRole('button', { name: 'Đang xử lý…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Đóng' })).toBeDisabled()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.getByRole('dialog')).toBeVisible()
    mock.onGet(records).reply(200, [record])
    await act(async () => complete([201, record]))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('retains confirmed success when refreshing history fails and blocks further writes', async () => {
    mock.onPost(records).reply(() => { mock.onGet(records).reply(503); return [201, record] })
    renderPage(); const form = await openRegister(); fireEvent.submit(form)
    expect(await screen.findByText('Đăng ký đề tài thành công.')).toBeVisible()
    expect(await screen.findByRole('alert')).toHaveTextContent('Dịch vụ tạm thời')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hủy đăng ký T1' })).toBeDisabled()
    expect(mock.history.post).toHaveLength(1)
  })

  it.each(['history', 'topics', 'register', 'cancel'] as const)('logs out on 401 from %s', async source => {
    if (source === 'history') mock.onGet(records).reply(401)
    if (source === 'topics') mock.onGet(available).reply(401)
    if (source === 'register') mock.onPost(records).reply(401)
    if (source === 'cancel') { mock.onGet(records).reply(200, [record]); mock.onDelete(records + 'R1/').reply(401) }
    renderPage()
    if (source === 'register') fireEvent.submit(await openRegister())
    if (source === 'cancel') { await ready(); fireEvent.click(screen.getByRole('button', { name: 'Hủy đăng ký T1' })); fireEvent.click(screen.getByRole('button', { name: 'Xác nhận hủy' })) }
    await waitFor(() => expect(logout).toHaveBeenCalledOnce())
  })

  it('aborts replaced topic loading and ignores its late unauthorized response', async () => {
    let complete!: (response: [number, unknown]) => void
    mock.onGet(available).reply(() => new Promise<[number, unknown]>(resolve => { complete = resolve }))
    renderPage()
    await waitFor(() => expect(mock.history.get.some(request => request.url === available)).toBe(true))
    const original = mock.history.get.find(request => request.url === available)!
    mock.onGet(available).reply(200, { results: topics, next_after: null })
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại' }))
    expect(await screen.findByText('Quản lý đồ án')).toBeVisible()
    expect(original.signal?.aborted).toBe(true)
    await act(async () => complete([401, {}]))
    expect(logout).not.toHaveBeenCalled()
  })

  it('aborts pending mutation on unmount and ignores late failure', async () => {
    let complete!: (response: [number, unknown]) => void
    mock.onPost(records).reply(() => new Promise<[number, unknown]>(resolve => { complete = resolve }))
    const view = renderPage(); fireEvent.submit(await openRegister())
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    view.unmount()
    expect(mock.history.post[0].signal?.aborted).toBe(true)
    await act(async () => complete([401, {}]))
    expect(logout).not.toHaveBeenCalled()
  })

  it('closes an idle dialog on Escape and restores opener focus', async () => {
    renderPage(); await openRegister()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đăng ký T1' })).toHaveFocus()
    expect(mock.history.post).toHaveLength(0)
  })
})

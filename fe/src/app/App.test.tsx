import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import MockAdapter from 'axios-mock-adapter'
import { Link, MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { SESSION_TOKEN_KEY } from '../features/auth/session-storage'
import { AuthProvider } from '../features/auth/AuthProvider'
import { apiClient, setAccessToken } from '../services/api-client'
import { App } from './App'

function RouteProbe() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <>
      <output data-testid="path">{location.pathname + location.search + location.hash}</output>
      <button onClick={() => navigate(-1)}>Back</button>
      <button onClick={() => navigate(1)}>Forward</button>
      {['/login', '/admin', '/lecture', '/student', '/', '/missing'].map((path) => (
        <Link key={path} to={path}>Go {path}</Link>
      ))}
    </>
  )
}

function renderApp(path: string | { pathname: string; state: unknown } = '/login') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
        <RouteProbe />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function fillForm(identifier = 'SV001', password = 'secret') {
  fireEvent.change(screen.getByLabelText('MSSV/UserID'), { target: { value: identifier } })
  fireEvent.change(screen.getByLabelText('Mật khẩu', { exact: true }), { target: { value: password } })
}

function submitForm() {
  fireEvent.submit(screen.getByRole('form', { name: 'Đăng nhập' }))
}

function responseForRole(role: number) {
  return {
    access: 'access-test-token', refresh: 'refresh-test-token', token_type: 'Bearer',
    user: { user_id: 'SV001', first_name: 'An', last_name: 'Nguyễn', role },
  }
}

const roles = [
  { role: 1, path: '/admin', title: 'Quản trị viên' },
  { role: 2, path: '/lecture', title: 'Giảng viên' },
  { role: 3, path: '/student', title: 'Sinh viên' },
]

describe('Login and role routes', () => {
  let mock: MockAdapter
  beforeEach(() => {
    setAccessToken(null)
    mock = new MockAdapter(apiClient, { onNoMatch: 'throwException' })
    mock.onGet('/registrations/api/v1/registrations/').reply(200, [])
    mock.onGet('/registrations/api/v1/available-topics/').reply(200, { results: [], next_after: null })
  })
  afterEach(() => {
    mock.restore()
    setAccessToken(null)
  })

  it('renders QNU branding and explains unavailable secondary actions without requests', () => {
    renderApp()
    expect(screen.getByRole('img', { name: 'Khuôn viên Trường Đại học Quy Nhơn' })).toHaveAttribute('src', '/img/banner_QNU.jpg')
    expect(screen.getByRole('img', { name: 'Logo Trường Đại học Quy Nhơn' })).toHaveAttribute('src', '/img/logo.png')
    expect(screen.getByRole('heading', { name: 'CỔNG THÔNG TIN ĐÀO TẠO' })).toBeVisible()
    for (const name of ['Đăng nhập với Google', 'Sinh viên quên mật khẩu']) {
      const button = screen.getByRole('button', { name })
      expect(button).toBeDisabled()
      expect(button).toHaveAccessibleDescription(/chưa khả dụng/)
      fireEvent.click(button)
    }
    expect(screen.queryByText('Vui lòng nhập MSSV/UserID.')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(mock.history.post).toHaveLength(0)
  })

  it('renders labeled credentials with password autocomplete and visibility control', () => {
    renderApp()
    expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(screen.getByLabelText('MSSV/UserID')).toHaveAttribute('autocomplete', 'username')
    const password = screen.getByLabelText('Mật khẩu', { exact: true })
    expect(password).toHaveAttribute('type', 'password')
    expect(password).toHaveAttribute('autocomplete', 'current-password')
    fireEvent.click(screen.getByRole('button', { name: 'Hiện mật khẩu' }))
    expect(password).toHaveAttribute('type', 'text')
    fireEvent.click(screen.getByRole('button', { name: 'Ẩn mật khẩu' }))
    expect(password).toHaveAttribute('type', 'password')
  })

  it('validates empty fields and focuses the identifier without making a request', () => {
    renderApp()
    fillForm('   ', '')
    submitForm()
    expect(screen.getByText('Vui lòng nhập MSSV/UserID.')).toBeVisible()
    expect(screen.getByText('Vui lòng nhập mật khẩu.')).toBeVisible()
    expect(screen.getByLabelText('MSSV/UserID')).toHaveFocus()
    expect(mock.history.post).toHaveLength(0)
  })

  it('validates an empty password independently', () => {
    renderApp()
    fillForm('SV001', '')
    submitForm()
    expect(screen.getByLabelText('Mật khẩu', { exact: true })).toHaveFocus()
    expect(screen.getByLabelText('Mật khẩu', { exact: true })).toHaveAttribute('aria-invalid', 'true')
    expect(mock.history.post).toHaveLength(0)
  })

  it.each(roles)('routes role $role to $path and attaches its token to subsequent API requests', async ({ role, path, title }) => {
    mock.onPost('/auth/login/').reply(200, responseForRole(role))
    mock.onGet('/auth/me/').reply(200, {})
    renderApp()
    fillForm('  SV001  ', ' secret ')
    submitForm()
    expect(await screen.findByRole('heading', { name: title })).toBeVisible()
    expect(screen.getByRole('navigation', { name: 'Chức năng' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Tổng quan' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByTestId('path')).toHaveTextContent(path)
    expect(JSON.parse(mock.history.post[0].data as string)).toEqual({ identifier: 'SV001', password: ' secret ' })
    expect(mock.history.post).toHaveLength(1)
    await apiClient.get('/auth/me/')
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer access-test-token')
    expect(localStorage.getItem('access')).toBeNull()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBe('access-test-token')
    expect(sessionStorage.length).toBe(1)
  })

  it('locks submission while pending and submits only once', async () => {
    let complete!: (response: [number, unknown]) => void
    mock.onPost('/auth/login/').reply(() => new Promise<[number, unknown]>((resolve) => { complete = resolve }))
    renderApp()
    fillForm()
    submitForm()
    submitForm()
    expect(screen.getByRole('button', { name: 'Đang đăng nhập…' })).toBeDisabled()
    expect(screen.getByLabelText('MSSV/UserID')).toBeDisabled()
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    await act(async () => complete([200, responseForRole(3)]))
    expect(await screen.findByRole('heading', { name: 'Sinh viên' })).toBeVisible()
  })

  it.each([
    { status: 401, message: 'MSSV/UserID hoặc mật khẩu không đúng.' },
    { status: 400, message: 'Thông tin đăng nhập không hợp lệ. Vui lòng kiểm tra lại.' },
    { status: 403, message: 'Bạn không có quyền thực hiện thao tác này.' },
    { status: 500, message: 'Không thể xử lý yêu cầu. Vui lòng thử lại sau.' },
  ])('shows safe feedback for HTTP $status and leaves the user unauthenticated', async ({ status, message }) => {
    mock.onPost('/auth/login/').reply(status, { detail: 'private server details' })
    mock.onGet('/probe/').reply(200, {})
    renderApp()
    fillForm()
    submitForm()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('button', { name: 'Đăng nhập' })).toBeEnabled()
    expect(screen.getByTestId('path')).toHaveTextContent('/login')
    await apiClient.get('/probe/')
    expect(mock.history.get.find(request => request.url === '/probe/')?.headers?.Authorization).toBeUndefined()
  })

  it.each(['network', 'timeout'])('shows a retryable error on %s failure', async (kind) => {
    const handler = mock.onPost('/auth/login/')
    if (kind === 'network') handler.networkError()
    else handler.timeout()
    renderApp()
    fillForm()
    submitForm()
    expect(await screen.findByRole('alert')).toHaveTextContent(kind === 'network' ? 'Không thể kết nối' : 'quá thời gian chờ')
    expect(screen.getByTestId('path')).toHaveTextContent('/login')
  })

  it.each([
    { data: responseForRole(8), message: 'Tài khoản chưa được cấp vai trò phù hợp.' },
    { data: { ...responseForRole(1), access: null }, message: 'Phản hồi đăng nhập không hợp lệ.' },
  ])('does not grant a session for invalid successful responses %#', async ({ data, message }) => {
    mock.onPost('/auth/login/').reply(200, data)
    mock.onGet('/probe/').reply(200, {})
    renderApp()
    fillForm()
    submitForm()
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    fireEvent.click(screen.getByRole('link', { name: 'Go /admin' }))
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/login'))
    await apiClient.get('/probe/')
    expect(mock.history.get[0].headers?.Authorization).toBeUndefined()
  })

  it.each(['/admin', '/lecture', '/student', '/'])('redirects an unauthenticated visit to %s back to login', async (path) => {
    renderApp(path)
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent('/login')
    expect(mock.history.get).toHaveLength(0)
  })

  it.each(roles)('keeps authenticated role $role on its own home when navigating to other roles/login', async ({ role, path }) => {
    mock.onPost('/auth/login/').reply(200, responseForRole(role))
    renderApp()
    fillForm()
    submitForm()
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent(path))
    for (const target of ['/login', '/admin', '/lecture', '/student', '/']) {
      fireEvent.click(screen.getByRole('link', { name: `Go ${target}` }))
      await waitFor(() => expect(screen.getByTestId('path').textContent).toBe(path))
    }
  })

  it('clears user and Bearer token on logout and protects the previous home', async () => {
    mock.onPost('/auth/login/').reply(200, responseForRole(3))
    mock.onGet('/probe/').reply(200, {})
    renderApp()
    fillForm()
    submitForm()
    fireEvent.click(await screen.findByRole('button', { name: 'Đăng xuất' }))
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
    await apiClient.get('/probe/')
    expect(mock.history.get.find(request => request.url === '/probe/')?.headers?.Authorization).toBeUndefined()
    fireEvent.click(screen.getByRole('link', { name: 'Go /student' }))
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/login'))
  })

  it('opens academic management for admin and clears the session on academic 401', async () => {
    mock.onPost('/auth/login/').reply(200, responseForRole(1))
    mock.onGet('/academic/api/departments/').reply(401)
    mock.onGet('/probe/').reply(200, {})
    renderApp()
    fillForm(); submitForm()
    fireEvent.click(await screen.findByRole('link', { name: 'Quản lý khoa' }))
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
    expect(mock.history.get[0].url).toBe('/academic/api/departments/')
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer access-test-token')
    await apiClient.get('/probe/')
    expect(mock.history.get.at(-1)?.headers?.Authorization).toBeUndefined()
  })

  it('connects all four admin menu items to their academic screens', async () => {
    mock.onPost('/auth/login/').reply(200, responseForRole(1))
    for (const resource of ['departments', 'majors', 'students', 'lecturers', 'sub-majors']) {
      mock.onGet(`/academic/api/${resource === 'students' || resource === 'lecturers' ? 'v1/' : ''}${resource}/`).reply(200, [])
    }
    renderApp()
    fillForm(); submitForm()
    await screen.findByRole('heading', { name: 'Quản trị viên' })
    for (const singular of ['khoa', 'ngành', 'sinh viên', 'giảng viên']) {
      fireEvent.click(screen.getByRole('link', { name: `Quản lý ${singular}` }))
      expect(await screen.findByRole('table', { name: `Danh sách ${singular}` })).toBeVisible()
      expect(screen.getByRole('button', { name: `Thêm ${singular}` })).toBeEnabled()
    }
  })

  function academicResponses() {
    for (const resource of ['departments', 'majors', 'students', 'lecturers', 'sub-majors']) {
      mock.onGet(`/academic/api/${resource === 'students' || resource === 'lecturers' ? 'v1/' : ''}${resource}/`).reply(200, [])
    }
  }

  it.each([
    { path: '/admin/departments', title: 'Quản lý khoa', list: 'khoa' },
    { path: '/admin/majors', title: 'Quản lý ngành', list: 'ngành' },
    { path: '/admin/students', title: 'Quản lý sinh viên', list: 'sinh viên' },
    { path: '/admin/lecturers', title: 'Quản lý giảng viên', list: 'giảng viên' },
  ])('restores a direct academic URL $path and keeps its active menu and breadcrumb', async ({ path, title, list }) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    let complete!: (response: [number, unknown]) => void
    mock.onGet('/auth/me/').reply(() => new Promise<[number, unknown]>((resolve) => { complete = resolve }))
    academicResponses()
    renderApp(path)
    expect(screen.getByTestId('path').textContent).toBe(path)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    await waitFor(() => expect(mock.history.get).toHaveLength(1))
    await act(async () => complete([200, responseForRole(1).user]))
    expect(await screen.findByRole('table', { name: `Danh sách ${list}` })).toBeVisible()
    expect(screen.getByRole('heading', { name: title, level: 1 })).toBeVisible()
    expect(screen.getByRole('link', { name: title })).toHaveAttribute('aria-current', 'page')
    expect(document.querySelector('.dash-breadcrumb strong')).toHaveTextContent(title)
    expect(screen.getByTestId('path').textContent).toBe(path)
  })

  it('returns to the requested page with query and hash after login', async () => {
    const destination = '/admin/students?source=bookmark#list'
    mock.onPost('/auth/login/').reply(200, responseForRole(1))
    academicResponses()
    renderApp(destination)
    await screen.findByRole('heading', { name: 'Đăng nhập' })
    fillForm(); submitForm()
    expect(await screen.findByRole('table', { name: 'Danh sách sinh viên' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe(destination)
  })

  it.each([
    'https://example.com/admin', '//example.com/admin', '/\\example.com/admin',
    '/student/profile', '/admin/missing', '/admin/%2F%2Fexample.com', '/admin\n', { path: '/admin/students' },
  ])('rejects unsafe or unauthorized login return state %#', async (from) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    renderApp({ pathname: '/login', state: { from } })
    expect(await screen.findByRole('heading', { name: 'Quản trị viên' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe('/admin')
  })

  it.each([
    { role: 1, path: '/admin/profile', title: 'Thông tin cá nhân' },
    { role: 2, path: '/lecture/profile', title: 'Thông tin cá nhân' },
    { role: 3, path: '/student/profile', title: 'Thông tin cá nhân' },
    { role: 1, path: '/admin/registrations', title: 'Quản lý đăng ký' },
  ])('opens the existing placeholder at $path', async ({ role, path, title }) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(role).user)
    renderApp(path)
    expect(await screen.findByRole('heading', { name: title, level: 1 })).toBeVisible()
    expect(screen.getByText('Đang phát triển')).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe(path)
  })

  it.each([2, 3])('blocks role %s from deep admin URLs without calling academic APIs', async (role) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(role).user)
    renderApp('/admin/students')
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe(role === 2 ? '/lecture' : '/student'))
    if (role === 3) await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })
    expect(mock.history.get.map(request => request.url)).toEqual(role === 3 ? [
      '/auth/me/', '/registrations/api/v1/registrations/', '/registrations/api/v1/available-topics/',
    ] : ['/auth/me/'])
  })

  it.each(['/student', '/student/registrations'])('opens student registration directly at %s with its saved JWT', async path => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(3).user)
    renderApp(path)
    expect(await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })).toBeVisible()
    expect(screen.getByRole('table', { name: 'Lịch sử đăng ký' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe(path)
    expect(screen.queryByText('Đang phát triển')).not.toBeInTheDocument()
    const requests = mock.history.get.filter(request => request.url?.startsWith('/registrations/'))
    expect(requests).toHaveLength(2)
    expect(requests.every(request => request.headers?.Authorization === 'Bearer saved-token')).toBe(true)
  })

  it('opens student registration from its menu and supports browser Back/Forward', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(3).user)
    renderApp('/student/profile')
    await screen.findByRole('heading', { name: 'Thông tin cá nhân', level: 1 })
    fireEvent.click(screen.getByRole('link', { name: 'Đăng ký đề tài' }))
    await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })
    expect(screen.getByRole('link', { name: 'Đăng ký đề tài' })).toHaveAttribute('aria-current', 'page')
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await screen.findByRole('heading', { name: 'Thông tin cá nhân', level: 1 })
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }))
    expect(await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })).toBeVisible()
  })

  it.each([1, 2])('blocks role %s from student registration without requesting its APIs', async role => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(role).user)
    renderApp('/student/registrations')
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe(role === 1 ? '/admin' : '/lecture'))
    expect(mock.history.get.some(request => request.url?.startsWith('/registrations/'))).toBe(false)
  })

  it('clears the actual student session when registration history returns 401', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(3).user)
    mock.onGet('/registrations/api/v1/registrations/').reply(401)
    renderApp('/student')
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it.each(['/missing', '/admin/missing'])('shows 404 and preserves the unknown URL %s', async (path) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    renderApp(path)
    expect(await screen.findByRole('heading', { name: '404 — Không tìm thấy trang' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe(path)
    fireEvent.click(screen.getByRole('link', { name: 'Về trang chủ' }))
    expect(await screen.findByRole('heading', { name: 'Quản trị viên' })).toBeVisible()
  })

  it('shows global 404 to guests without redirecting to login', () => {
    renderApp('/missing')
    expect(screen.getByRole('heading', { name: '404 — Không tìm thấy trang' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe('/missing')
  })

  it('follows Back and Forward with the correct academic screen and active menu', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    academicResponses()
    renderApp('/admin')
    fireEvent.click(await screen.findByRole('link', { name: 'Quản lý khoa' }))
    await screen.findByRole('table', { name: 'Danh sách khoa' })
    fireEvent.click(screen.getByRole('link', { name: 'Quản lý sinh viên' }))
    await screen.findByRole('table', { name: 'Danh sách sinh viên' })
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(await screen.findByRole('table', { name: 'Danh sách khoa' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Quản lý khoa' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Quản lý sinh viên' })).not.toHaveAttribute('aria-current')
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }))
    expect(await screen.findByRole('table', { name: 'Danh sách sinh viên' })).toBeVisible()
    expect(screen.getByTestId('path').textContent).toBe('/admin/students')
  })

  it.each([
    { role: 1, path: '/admin/topics' },
    { role: 2, path: '/lecture/topics' },
  ])('restores topic deep link $path with role-appropriate controls', async ({ role, path }) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(role).user)
    mock.onGet('/topics/api/v1/topics/').reply(200, [{ req_GPA: 0, studentQuota: 1, status: 1, topic_id: 'DT001', name: 'SOA', description: null, major_name: 'IT', avisor_name: 'An' }])
    renderApp(path)
    expect(await screen.findByRole('table', { name: 'Danh sách đề tài' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Quản lý đề tài', level: 1 })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Quản lý đề tài' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByTestId('path').textContent).toBe(path)
    expect(screen.getByRole('button', { name: 'Xem chi tiết DT001' })).toBeEnabled()
    for (const name of ['Tạo đề tài', 'Sửa DT001', 'Xóa DT001']) {
      if (role === 1) expect(screen.getByRole('button', { name })).toBeEnabled()
      else expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    expect(mock.history.get.find(request => request.url === '/topics/api/v1/topics/')?.headers?.Authorization).toBe('Bearer saved-token')
  })

  it('returns to the topic route after login then follows Back/Forward navigation', async () => {
    mock.onPost('/auth/login/').reply(200, responseForRole(1))
    mock.onGet('/topics/api/v1/topics/').reply(200, [])
    academicResponses()
    renderApp('/admin/topics')
    await screen.findByRole('heading', { name: 'Đăng nhập' })
    fillForm(); submitForm()
    await screen.findByRole('table', { name: 'Danh sách đề tài' })
    expect(screen.getByTestId('path').textContent).toBe('/admin/topics')
    fireEvent.click(screen.getByRole('link', { name: 'Quản lý khoa' }))
    await screen.findByRole('table', { name: 'Danh sách khoa' })
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await screen.findByRole('table', { name: 'Danh sách đề tài' })
    expect(screen.getByRole('link', { name: 'Quản lý đề tài' })).toHaveAttribute('aria-current', 'page')
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }))
    await screen.findByRole('table', { name: 'Danh sách khoa' })
    expect(screen.getByTestId('path').textContent).toBe('/admin/departments')
  })

  it('blocks student access to topic management before any topic request', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(3).user)
    renderApp('/admin/topics')
    expect(await screen.findByRole('heading', { name: 'Sinh viên' })).toBeVisible()
    await screen.findByRole('table', { name: 'Đề tài mở đăng ký' })
    expect(mock.history.get.some(request => request.url?.startsWith('/topics/'))).toBe(false)
    expect(mock.history.get.map(request => request.url)).toEqual([
      '/auth/me/', '/registrations/api/v1/registrations/', '/registrations/api/v1/available-topics/',
    ])
  })

  it('clears the real auth session if the topic API returns 401', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    mock.onGet('/topics/api/v1/topics/').reply(401)
    renderApp('/admin/topics')
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it('aborts an academic request when navigating to another page', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    academicResponses()
    let complete!: (response: [number, unknown]) => void
    mock.onGet('/academic/api/departments/').reply(() => new Promise<[number, unknown]>((resolve) => { complete = resolve }))
    renderApp('/admin/departments')
    await waitFor(() => expect(mock.history.get.some(request => request.url === '/academic/api/departments/')).toBe(true))
    const request = mock.history.get.find(request => request.url === '/academic/api/departments/')!
    fireEvent.click(screen.getByRole('link', { name: 'Quản lý sinh viên' }))
    await screen.findByRole('table', { name: 'Danh sách sinh viên' })
    expect(request.signal?.aborted).toBe(true)
    await act(async () => complete([401, {}]))
    expect(screen.getByTestId('path').textContent).toBe('/admin/students')
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBe('saved-token')
  })

  it('cancels login if the form is unmounted before a response arrives', async () => {
    let complete!: (response: [number, unknown]) => void
    mock.onPost('/auth/login/').reply(() => new Promise<[number, unknown]>((resolve) => { complete = resolve }))
    mock.onGet('/probe/').reply(200, {})
    renderApp()
    fillForm()
    submitForm()
    await waitFor(() => expect(mock.history.post).toHaveLength(1))
    fireEvent.click(screen.getByRole('link', { name: 'Go /admin' }))
    await act(async () => complete([200, responseForRole(1)]))
    expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent('/login')
    await apiClient.get('/probe/')
    expect(mock.history.get[0].headers?.Authorization).toBeUndefined()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it.each(roles)('restores role $role after F5 without prematurely redirecting', async ({ role, path, title }) => {
    mock.onPost('/auth/login/').reply(200, responseForRole(role))
    const first = renderApp()
    fillForm(); submitForm()
    await screen.findByRole('heading', { name: title })
    first.unmount()
    mock.resetHistory()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBe('access-test-token')
    let complete!: (response: [number, unknown]) => void
    mock.onGet('/auth/me/').reply(() => new Promise<[number, unknown]>((resolve) => { complete = resolve }))
    renderApp(path)
    expect(screen.getByText('Đang xác thực phiên đăng nhập…')).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent(path)
    expect(screen.queryByRole('heading', { name: 'Đăng nhập' })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    await waitFor(() => expect(mock.history.get).toHaveLength(1))
    expect(mock.history.get[0].headers?.Authorization).toBe('Bearer access-test-token')
    await act(async () => complete([200, responseForRole(role).user]))
    expect(await screen.findByRole('heading', { name: title })).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent(path)
  })

  it.each(['/admin', '/login'])('uses the server role when restoring at %s', async (path) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(3).user)
    renderApp(path)
    expect(await screen.findByRole('heading', { name: 'Sinh viên' })).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent('/student')
  })

  it.each([401, 403, 'malformed', 'invalid-role'] as const)('clears an invalid restored session: %s', async (failure) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'invalid-token')
    mock.onGet('/auth/me/').reply(typeof failure === 'number' ? failure : 200, failure === 'invalid-role' ? responseForRole(9).user : {})
    renderApp('/admin')
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it.each(['network', 'timeout', '503'] as const)('retains the token and allows explicit retry after restore %s', async (failure) => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    const handler = mock.onGet('/auth/me/')
    if (failure === 'network') handler.networkError()
    else if (failure === 'timeout') handler.timeout()
    else handler.reply(503)
    renderApp('/admin')
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.getByTestId('path')).toHaveTextContent('/admin')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBe('saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByRole('heading', { name: 'Quản trị viên' })).toBeVisible()
    expect(mock.history.get).toHaveLength(2)
  })

  it('can abandon a failed restore and return to login', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(503)
    renderApp('/admin')
    fireEvent.click(await screen.findByRole('button', { name: 'Về đăng nhập' }))
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it('restores safely under StrictMode and clears persistence after logout', async () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'saved-token')
    mock.onGet('/auth/me/').reply(200, responseForRole(1).user)
    render(<StrictMode><MemoryRouter initialEntries={['/admin']}><AuthProvider><App /></AuthProvider></MemoryRouter></StrictMode>)
    expect(await screen.findByRole('heading', { name: 'Quản trị viên' })).toBeVisible()
    expect(mock.history.get).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }))
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
    expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
  })

  it('continues login with a visible warning if session storage writes are denied', async () => {
    mock.onPost('/auth/login/').reply(200, responseForRole(1))
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied') })
    try {
      renderApp(); fillForm(); submitForm()
      expect(await screen.findByRole('heading', { name: 'Quản trị viên' })).toBeVisible()
      expect(screen.getByText(/Trình duyệt không cho phép lưu phiên/)).toBeVisible()
      expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull()
    } finally { write.mockRestore() }
  })
})


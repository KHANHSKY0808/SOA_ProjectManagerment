# Frontend — Quản lý đồ án tốt nghiệp

React + Vite + TypeScript, dùng npm, React Router và Axios client chung. Đã triển khai đăng nhập, bảo vệ route theo role và dashboard chung. Quản trị viên có thể quản lý khoa, ngành, sinh viên, giảng viên và quản lý đề tài qua API Gateway. Giảng viên chỉ xem đề tài được phân hướng dẫn và chấm/sửa điểm sinh viên thuộc đề tài đó; không được tạo, sửa, xóa đề tài hoặc hủy đăng ký sinh viên. Các luồng được kiểm thử bằng API mock; chưa xác minh với tài khoản backend thực tế.

## Chạy tại máy

Dùng Node.js 24 LTS (CI dùng Node 24). Từ thư mục repository:

```powershell
cd fe
npm ci
Copy-Item .env.example .env
npm run dev
```

Mở `http://localhost:5173`. Cổng dev được cố định; nếu đang bận, dừng tiến trình đang sử dụng cổng hoặc truyền `--port` khác. Khi thay đổi `.env`, khởi động lại Vite.

| Lệnh | Chức năng |
| --- | --- |
| `npm run dev` | Chạy Vite dev server |
| `npm run build` | Kiểm tra TypeScript và build vào `dist/` |
| `npm run preview` | Xem bản build trên máy |
| `npm run lint` | Kiểm tra ESLint |
| `npm run typecheck` | Kiểm tra TypeScript riêng |
| `npm run test` | Chạy toàn bộ test một lần |
| `npm run test:watch` | Chạy test khi sửa file |

## Cấu trúc

```text
src/
  app/                  # Routes, trang đích theo role và integration tests
  config/               # Gateway dev proxy và test HTTP qua Vite thật
  features/auth/        # Login, DTO/API, auth context/provider, route guards
  features/academic/    # DTO/API, CRUD học vụ, cấu hình form, CSS và tests
  services/
    api-client.ts       # Axios instance và quản lý access token trong bộ nhớ
    api-error.ts        # ApiError và chuẩn hóa lỗi
    api-client.test.ts  # Test qua mock adapter, không gọi backend
  styles/global.css
  test/setup.ts
  main.tsx
  vite-env.d.ts
```

Thêm `features/<feature>/` cho từng nghiệp vụ và `components/` cho thành phần dùng chung khi cần.

## Đăng nhập và route graph

```text
/
  ├─ chưa đăng nhập -> /login
  └─ đã đăng nhập -> trang tương ứng role

/login -- POST /auth/login/ --> role từ response
  ├─ 1 -> /admin   (Quản trị viên)
  ├─ 2 -> /lecture (Giảng viên)
  └─ 3 -> /student (Sinh viên)

Protected route
  ├─ chưa đăng nhập -> /login (ghi nhớ URL đã yêu cầu)
  ├─ sai role -> trang tương ứng role của tài khoản
  └─ đúng role -> hiển thị trang

Đường dẫn không tồn tại -> trang 404
Đăng xuất -> xóa user/access token -> /login
```

Các trang dùng nested routes và `Outlet`; menu, shortcut và mục tài khoản dùng `Link`/`NavLink`. URL là nguồn xác định trang, tiêu đề, breadcrumb và menu đang chọn. Back/Forward cập nhật trang tương ứng.

| URL | Nội dung | Role |
| --- | --- | --- |
| `/admin`, `/lecture` | Tổng quan theo vai trò | 1, 2 tương ứng |
| `/student` | Đề tài mở, đăng ký hiện tại và lịch sử đăng ký | 3 |
| `/admin/departments` | Quản lý khoa | 1 |
| `/admin/majors` | Quản lý ngành | 1 |
| `/admin/students` | Quản lý sinh viên | 1 |
| `/admin/lecturers` | Quản lý giảng viên | 1 |
| `/admin/profile`, `/lecture/profile`, `/student/profile` | Thông tin cá nhân — Đang phát triển | Theo vai trò |
| `/admin/topics` | Danh sách, chi tiết, thêm, sửa, xóa đề tài | 1 |
| `/admin/registrations` | Đăng ký — Đang phát triển | 1 |
| `/lecture/topics` | Danh sách, chi tiết, thêm, sửa, xóa đề tài | 2 |
| `/student/registrations` | Cùng giao diện đăng ký đề tài với `/student` | 3 |

Khi truy cập trang bảo vệ lúc chưa đăng nhập, frontend ghi URL vào router state và chuyển sang `/login`. Đăng nhập thành công quay về URL đã yêu cầu nếu đây là route đã biết và đúng vai trò; giữ query/hash. Địa chỉ ngoài ứng dụng, đường dẫn không hợp lệ hoặc sai vai trò chuyển về tổng quan của tài khoản. State này không được lưu riêng qua reload trang login. URL không tồn tại hiển thị 404; đường dẫn dưới role vẫn qua guard trước khi hiển thị 404.

Form nhận MSSV/UserID và mật khẩu; có hiện/ẩn mật khẩu, validation, trạng thái đang gửi và thông báo lỗi an toàn. MSSV phải là UserID của tài khoản vì backend không cung cấp lookup riêng theo MSSV. Không có chọn role: role lấy từ response auth-service.

Request qua Axios/Gateway:

```http
POST /auth/login/
Content-Type: application/json
```

```json
{ "identifier": "SV001", "password": "your-password" }
```

Response contract theo [auth-service README](../services/auth-service/README.md):

```json
{
  "access": "<JWT access token>",
  "refresh": "<JWT refresh token>",
  "token_type": "Bearer",
  "user": {
    "user_id": "SV001",
    "first_name": "An",
    "last_name": "Nguyen",
    "role": 3
  }
}
```

Ví dụ trên chỉ hiển thị các field identity được frontend sử dụng; DTO backend có thêm các field được mô tả trong service README. `identifier` được trim, password giữ nguyên. HTTP 400/422 báo dữ liệu không hợp lệ; 401 báo sai thông tin đăng nhập; lỗi network/timeout hiển thị thông báo thử lại. Response thiếu field cần thiết hoặc role ngoài số 1/2/3 không tạo session.

`AuthProvider` giữ user và access token trong bộ nhớ; đồng thời lưu **chỉ access token** vào `sessionStorage` với key `graduation-project.auth.access.v1`. Không lưu password, refresh token, user/profile hoặc role; không dùng localStorage và không refresh token tự động. Axios gắn Bearer từ bộ nhớ cho các request.

Khi **F5/reload trong cùng tab**, frontend đọc token đã lưu và gọi `GET /auth/me/` để xác thực và lấy user/role hiện tại. Trong lúc chờ, route hiển thị “Đang xác thực phiên đăng nhập…” và chưa mở dashboard hoặc chuyển sang login. Phiên hợp lệ giữ đăng nhập; 401/403 hoặc response profile không hợp lệ xóa phiên và về login. Lỗi network/timeout/5xx hiển thị màn hình có **Thử lại** hoặc **Về đăng nhập**, giữ token đã lưu nhưng chưa cho truy cập trang bảo vệ. Mỗi lần khôi phục chỉ có một request đang chờ, không tự retry.

Token vẫn hết hạn theo backend: reload sau khi hết hạn cần đăng nhập lại. sessionStorage theo phiên tab, không phải chức năng “ghi nhớ đăng nhập”; đóng tab thường kết thúc phiên lưu, nhưng trình duyệt có thể giữ dữ liệu khi khôi phục/nhân bản tab. Nếu trình duyệt chặn lưu trữ, phiên hiện tại vẫn dùng được và có cảnh báo rằng reload có thể cần đăng nhập lại. Token đọc được bằng JavaScript nên vẫn chịu rủi ro XSS; không đưa dữ liệu không tin cậy vào HTML hoặc log token.

Đăng xuất xóa token trong bộ nhớ và sessionStorage, không gọi API thu hồi vì backend chưa có contract logout/revocation. Logout, phiên mới và unmount hủy request khôi phục; phản hồi đến muộn không được tạo lại phiên. Unmount do reload giữ sessionStorage để lần tải sau có thể khôi phục. Backend chịu trách nhiệm xác thực JWT, hạn token và quyền truy cập; frontend guard chỉ kiểm soát điều hướng.

Các màn hình học vụ xử lý 401 bằng logout để xóa phiên và đưa người dùng về đăng nhập. Lỗi 403 giữ phiên và hiển thị thông báo thiếu quyền; frontend không thay thế kiểm tra quyền ở backend.

Production hosting phải trả `index.html` cho `/login`, các đường dẫn SPA `/admin/*`, `/lecture/*`, `/student/*` và URL frontend không tồn tại để React Router hiển thị 404 (kể cả khi mở trực tiếp hoặc F5). Giữ API prefixes chuyển đến Gateway, không rewrite API thành HTML. Không thay đổi cổng hoặc route backend.

## Cấu hình Gateway

```dotenv
VITE_API_BASE_URL=/
VITE_API_PROXY_TARGET=http://localhost:8000
```

Mọi API request phải dùng đường dẫn Gateway. Giữ nguyên các prefix `/auth/*`, `/academic/*`, `/registrations/*` theo contract của backend; không gọi trực tiếp cổng service hoặc Consul từ trình duyệt. Các route khác chỉ được thêm khi đã xác minh contract.

Axios mặc định dùng `/` để request cùng origin với frontend. Trong development, Vite proxy các prefix `/auth`, `/academic`, `/registrations`, `/topics` đến Gateway được cấu hình bằng `VITE_API_PROXY_TARGET` (mặc định `http://localhost:8000`). Giữ nguyên đường dẫn, method, JSON body và Bearer token; Gateway tiếp tục chịu trách nhiệm route đến service. Các đường dẫn frontend `/login`, `/admin/*`, `/lecture/*`, `/student/*` không đi qua proxy.

```text
Browser http://localhost:5173/auth/login/
  -> Vite proxy http://localhost:8000/auth/login/
  -> API Gateway -> auth-service /login/
```

Browser chỉ gọi origin frontend nên development không cần CORS tại Gateway. Gateway và auth-service vẫn phải chạy/healthy để đăng nhập thực tế. Không cấu hình lại `VITE_API_BASE_URL=http://localhost:8000` khi muốn dùng proxy: URL tuyệt đối sẽ bỏ qua Vite và lại cần Gateway CORS.

Sau khi cập nhật `.env` hoặc proxy config, dừng Vite bằng Ctrl+C rồi chạy lại `npm run dev`. Không cần restart Gateway cho thay đổi frontend proxy.

Vite proxy phục vụ development, không được đóng gói vào `dist/`. Khi deploy production với `VITE_API_BASE_URL=/`, web server phải chuyển tiếp các API prefix trên cùng origin đến Gateway và trả SPA HTML cho route frontend. Nếu chọn API URL tuyệt đối, cấu hình CORS tại server cho origin production. Vite thay thế biến môi trường lúc build; sửa biến trên máy chủ sau build không thay đổi bundle. Dùng HTTPS trong production. Mọi biến `VITE_*` là cấu hình public, không chứa signing key, mật khẩu hoặc tokens.

## Dùng Axios client

```ts
import { apiClient, setAccessToken } from './services/api-client'
import { ApiError } from './services/api-error'

// AuthProvider đã thực hiện việc này cho luồng đăng nhập hiện tại.
setAccessToken(accessToken)

// Ví dụ đọc health qua Gateway; kiểu dữ liệu cần theo DTO thực tế.
const response = await apiClient.get<unknown>('/auth/health/')
const data = response.data

// Với giao diện hiện tại, dùng useAuth().logout() để xóa cả user và token.
setAccessToken(null)

try {
  await apiClient.get('/auth/me/')
} catch (error: unknown) {
  if (error instanceof ApiError) {
    // error.kind: http | network | timeout | cancelled | unknown
    // error.status: HTTP status nếu có
    // error.message: thông báo an toàn để hiển thị
    // error.details: dữ liệu response chưa xác thực kiểu, dùng cho lỗi field
  }
}
```

Client giữ chuẩn Axios: trả về `AxiosResponse<T>`, đọc DTO tại `response.data`. `Accept: application/json` là mặc định; Axios tự thiết lập Content-Type khi gửi JSON hoặc FormData. Timeout là 10 giây. Request nhận Bearer token từ bộ nhớ; `AuthProvider` quản lý lưu token theo tab và khôi phục khi reload qua `/auth/me/`. Không có refresh tự động hoặc retry; caller xử lý `401` bằng logout để xóa cả token lưu trong tab. Dùng `AbortController` và tùy chọn `signal` để hủy request.

Chỉ truyền URL tương đối thuộc Gateway vào instance này; không dùng nó cho dịch vụ ngoài vì interceptor sẽ đính kèm token. Không log token hoặc toàn bộ lỗi response; không hiển thị trực tiếp `details` như HTML. Authorization và validation nghiệp vụ vẫn thuộc backend.

## Kiểm thử và CI

```powershell
npm run lint
npm run test
npm run build
```

Vitest, Testing Library và Axios Mock Adapter kiểm tra login, payload/response DTO, cả ba role, route guards, logout, duplicate submits, validation, lỗi HTTP/network/timeout và cancellation. Các test Axios kiểm tra gắn/xóa Bearer token, xử lý lỗi và base URL mặc định/override. Test proxy khởi tạo Vite thật và Gateway giả lập trên các cổng loopback tạm thời để xác nhận đường dẫn, query, method/body/header, status lỗi và SPA fallback; server tự đóng sau test. Không cần Django, Gateway thật hoặc database. Frontend CI nằm tại `../.github/workflows/frontend-tests.yml`; Python CI giữ nguyên.

Không chạy Django checks cho thay đổi chỉ thuộc frontend. Test mock không xác nhận CORS hoặc tích hợp đăng nhập với service đang chạy; cần kiểm thử bằng tài khoản hợp lệ qua Gateway trong môi trường triển khai.

Tài liệu chính thức: [Vite](https://vite.dev/guide/), [Axios instance](https://axios-http.com/docs/instance), [Vitest](https://vitest.dev/guide/), [React Router](https://reactrouter.com/start/declarative/routing).

## Dashboard theo vai trò

`/admin`, `/lecture`, `/student` dùng `src/components/layout/MainLayout.tsx` với màu chủ đạo `#363199` và trắng. Header có tên trường, nút đóng/mở sidebar, bảng thông báo và bảng tài khoản. Sidebar hiển thị tên, UserID và vai trò từ phiên đăng nhập, các nhóm menu đóng/mở độc lập, mục đang chọn và nút đăng xuất.

Menu nghiệp vụ nằm trong `src/components/layout/dashboard-menu.ts`:

- Role 1 (quản trị viên): **Học vụ** gồm Quản lý khoa, Quản lý ngành, Quản lý sinh viên, Quản lý giảng viên; **Đề tài** gồm Quản lý đề tài, Quản lý đăng ký.
- Role 2 (giảng viên): **Đề tài** gồm Quản lý đề tài.
- Role 3 (sinh viên): mục **Đăng ký đề tài** trực tiếp, không có tiêu đề nhóm.

Các vai trò giữ Tổng quan và Đăng xuất. Sidebar không còn nhóm Trang cá nhân hoặc các mục học vụ/hướng dẫn cũ. Thông tin cá nhân truy cập từ bảng tài khoản trên header hoặc nút “Thông tin của tôi” ở trang tổng quan, độc lập với thứ tự menu nghiệp vụ. Trang tổng quan có lời chào, tối đa ba truy cập nhanh lấy từ menu của vai trò hiện tại và thông tin tài khoản.

Việc chọn mục menu điều hướng tới route con tương ứng. Bốn mục học vụ của quản trị viên hiển thị màn hình CRUD. Quản lý đề tài hỗ trợ danh sách, chi tiết, tạo, sửa và xóa cho admin; giảng viên chỉ xem đề tài được phân hướng dẫn và chấm điểm. Thông tin cá nhân và đăng ký quản trị vẫn hiển thị “Đang phát triển”. Reload giữ nguyên URL và trang hiện tại khi token theo tab còn hợp lệ và `/auth/me/` xác thực thành công. Nội dung form và từ khóa tìm kiếm không được lưu qua reload. Chưa có API thông báo. Logo đang dùng chữ QNU tạm thời.

Trên màn hình rộng hơn 800px, sidebar mặc định mở và có thể ẩn. Ở màn hình nhỏ, sidebar mặc định đóng, mở dưới dạng drawer với nền che, khóa cuộn trang, giữ focus bàn phím bên trong và đóng bằng Escape/nút đóng/nhấn nền che/chọn mục. Các bảng trên header đóng bằng Escape hoặc nhấn ra ngoài. Có liên kết bỏ qua điều hướng để đến nội dung chính.

Test layout kiểm tra menu/identity của cả ba vai trò, fallback tên, sidebar, nhóm menu, chọn mục, truy cập nhanh, thông báo/tài khoản, logout, drawer mobile và thay đổi breakpoint. Integration tests tiếp tục kiểm tra đăng nhập, role guards và xóa token khi đăng xuất. Chạy `npm run lint`, `npm run test`, `npm run build` để xác minh.

## Quản lý học vụ

Đăng nhập role **1**, mở nhóm **HỌC VỤ** và chọn khoa, ngành, sinh viên hoặc giảng viên. Mỗi chức năng có page riêng, danh sách, tìm kiếm trên dữ liệu đã tải, tải lại, thêm, sửa và xác nhận xóa. API danh sách hiện trả mảng đầy đủ; chưa có phân trang phía server. Bảng hỗ trợ cuộn ngang trên màn hình nhỏ.

Nhập từ khóa rồi bấm **Search** (hoặc Enter trong ô tìm kiếm) để áp dụng bộ lọc. Gõ hoặc xóa từ khóa chưa thay đổi kết quả; gửi từ khóa trống để hiện tất cả bản ghi. Cả bốn trang tìm theo mã hoặc tên, không phân biệt hoa thường. Tên sinh viên/giảng viên ghép họ rồi tên từ user DTO. Không tìm theo tên khoa/ngành liên quan, GPA hoặc tín chỉ.

**Thêm/Sửa** mở popup có nhãn trường, lỗi validation và lỗi API bên trong. Có nút Lưu, Hủy, Đóng; Escape đóng khi chưa gửi. Popup giữ focus bàn phím bên trong, khóa tương tác/cuộn nền và trả focus về nút mở khi đóng nếu nút còn dùng được. Trong khi lưu, không thể đóng hoặc gửi lặp. Lưu thành công và hoàn tất tải lại sẽ đóng popup.

Các page nằm tại `features/academic/pages/DepartmentPage.tsx`, `MajorPage.tsx`, `StudentPage.tsx`, `LecturerPage.tsx`. Mỗi page khai báo cột, trường form và trường tìm kiếm riêng. `components/` chứa `AcademicSearch`, `AcademicTable`, `AcademicFormField`, `Modal`, `DeleteConfirmation` và khung hiển thị `AcademicManagementView`; `useAcademicManagement.ts` quản lý vòng đời request và trạng thái CRUD dùng chung. `AcademicRoutePage` render từng page qua các route con của `/admin`; chuyển trang unmount page cũ và hủy request đang chờ. `DashboardHomePage` và `DashboardPlaceholderPage` nhận dữ liệu layout qua Outlet context; metadata menu/URL tập trung tại `components/layout/dashboard-menu.ts`.

| Màn hình | Gateway endpoint | Trường DTO |
| --- | --- | --- |
| Khoa | `/academic/api/departments/` | `department_id`, `name` |
| Ngành | `/academic/api/majors/` | `major_id`, `name`, `department_id` |
| Sinh viên | `/academic/api/v1/students/` | `student_id`, `major_id`, `sub_major_id`, `accumulated_credits`, `gpa`, `user` |
| Giảng viên | `/academic/api/v1/lecturers/` | `lecturer_id`, `department_id`, `user` |

Danh sách dùng GET, thêm dùng POST, sửa dùng PATCH và xóa dùng DELETE tại `{endpoint}{id}/`. ID được giữ nguyên khi sửa. Request dùng Axios client chung, Bearer token trong bộ nhớ và timeout 10 giây; không tự retry thao tác ghi. Khi chuyển màn hình, request đang chờ được hủy và phản hồi cũ không cập nhật màn hình mới.

Khoa/ngành được tải làm lựa chọn quan hệ. Sinh viên chọn ngành và chuyên ngành từ `/academic/api/majors/` và `/academic/api/sub-majors/`; chuyên ngành lọc theo ngành, được xóa lựa chọn khi đổi ngành. Không có màn hình CRUD chuyên ngành trong phạm vi này. Quan hệ không bắt buộc có thể bỏ chọn và được gửi `null`; GPA là số hữu hạn, tín chỉ là số nguyên. Quy tắc nghiệp vụ và ràng buộc tham chiếu vẫn do backend xác nhận.

**Giới hạn ID:** khoa/ngành vẫn dùng route số nguyên không âm ở dạng chuẩn. API v1 sinh viên/giảng viên hỗ trợ mã chữ như `SV001`, `GV001`; mã không được chứa dấu phân cách đường dẫn hoặc chỉ là `.`/`..` và không đổi khi sửa.

Popup sinh viên/giảng viên dùng `UserProfileFields` chung: họ, tên, giới tính, ngày sinh, email, số điện thoại, trạng thái và mật khẩu. Thêm tạo cả tài khoản và hồ sơ; role tự gán 3/2. Mật khẩu bắt buộc khi thêm, để trống khi sửa sẽ không gửi trường password và giữ nguyên mật khẩu cũ; mật khẩu không bao giờ được trả từ API. Giới tính dùng select Nam = 1, Nữ = 0; trạng thái dùng select Hoạt động = 1, Khóa = 0. API nhận mã số, không nhận nhãn. Giữ lựa chọn trống (null) và hiển thị giá trị cũ ngoài danh sách để tránh tự thay đổi dữ liệu khi sửa. Thay đổi này chỉ cập nhật form, không thêm chính sách khóa đăng nhập ở backend. CreatedAt/UpdatedAt do server tạo.

Xóa thành công nghĩa là xóa cả hồ sơ và tài khoản; dữ liệu có tham chiếu có thể bị từ chối (409). Lỗi 400, kể cả trường `user.*`, hiển thị dưới form. `operation_incomplete` báo cần tải lại và kiểm tra cả hai service trước khi thử lại; không tự gửi lại thao tác ghi. Form giữ dữ liệu khi thất bại. Nếu ghi thành công nhưng tải lại thất bại, thông báo lưu thành công và lỗi tải lại cùng hiển thị. Cần cấu hình `INTERNAL_SERVICE_TOKEN` khớp ở auth/academic, không đặt secret trong biến VITE hoặc trình duyệt. Xem hợp đồng và xử lý sự cố tại [academic README](../services/academic-services/README.md#composite-studentlecturer-management-v1).

Tests học vụ dùng Axios Mock Adapter và Testing Library để kiểm tra CRUD của cả bốn page, DTO/method/path/Bearer, quan hệ nullable, tìm kiếm chỉ khi submit và loại trừ trường không liên quan, popup thêm/sửa, focus/trap/return, Escape/Hủy/Đóng, khóa popup khi đang lưu, giới hạn ID, lọc chuyên ngành, validation, lỗi HTTP/network/timeout, chống gửi lặp và hủy request. Integration test kiểm tra bốn menu mở đúng page và academic 401 xóa session/token. Các test này không xác minh kết nối Gateway/Consul/database thực tế.

### Giao diện đăng nhập QNU

Trang login sử dụng banner `public/img/banner_QNU.jpg` và logo `public/img/logo.png` theo mẫu QNU. Logo cũng được dùng làm favicon và thương hiệu sidebar; các icon chức năng, menu theo vai trò và API đăng nhập giữ nguyên. Trên màn hình nhỏ, banner ẩn để ưu tiên biểu mẫu. Nút Google và quên mật khẩu đang vô hiệu hóa, có giải thích và hướng dẫn liên hệ phòng đào tạo vì chưa tích hợp các luồng này.

## Danh sách và tạo đề tài

`/admin/topics` cho role 1 quản lý mọi đề tài. `/lecture/topics` cho role 2 chỉ xem đề tài được phân hướng dẫn; API lọc theo `advisor_id` bằng JWT `user_id` và trả 404 khi đọc chi tiết ngoài phạm vi. Giảng viên không có nút tạo/sửa/xóa đề tài; API cũng chặn các thao tác này với 403. Role 3 không có route quản lý đề tài; API giữ quyền chỉ đọc. Bảng có bốn cột dữ liệu **Mã đề tài**, **Tên đề tài**, **Giáo viên hướng dẫn**, **Tên ngành**, cùng cột **Thao tác**. Dữ liệu lấy từ `GET /topics/api/v1/topics/`; cột tên dùng đúng trường response `avisor_name` và `major_name`. Tên null hoặc rỗng hiển thị `—`. Chỉ lọc theo mã/tên khi nhấn **Search** hoặc submit form tìm kiếm; nhập chữ không tự lọc. Bộ lọc chạy trên danh sách đã tải.

Popup tạo có tên (bắt buộc), mô tả (textarea, có thể bỏ trống), select giáo viên hướng dẫn và select ngành (bắt buộc). Ngành được bổ sung vì POST hiện yêu cầu `major_id`; không suy ra ngành từ khoa của giảng viên. Giảng viên lấy từ `/academic/api/v1/lecturers/`, dùng tên trong `user` và mã để phân biệt; thiếu tên hiển thị mã. Ngành lấy từ `/academic/api/majors/`; mã chữ bị vô hiệu hóa vì topic-service hiện chỉ xác thực được ngành có mã số. Không tự chọn ngành mặc định.

Frontend sinh UUID v4 một lần khi mở bản nháp: dùng `crypto.randomUUID()` khi có, hoặc `crypto.getRandomValues()` để hỗ trợ origin HTTP khi `randomUUID()` không khả dụng. Cả hai dùng nguồn ngẫu nhiên mật mã; không dùng `Math.random()` hoặc thời gian làm mã. Nếu trình duyệt không có nguồn ngẫu nhiên phù hợp, frontend báo lỗi và không gửi POST. Production vẫn cần HTTPS. Mã không có ô nhập và giữ nguyên khi có lỗi gửi. `POST /topics/api/v1/topics/` gửi các trường:

```json
{
  "topic_id": "68317f4b-7445-45bf-8cbb-0c3ba05c5a50",
  "name": "Quản lý đồ án tốt nghiệp",
  "description": "Ứng dụng SOA",
  "advisor_id": "GV001",
  "major_id": "2"
}
```

Các request dùng Axios/Gateway và Bearer JWT hiện tại, timeout 10 giây; không gọi trực tiếp service. Backend chỉ cho JWT role 1 ghi dữ liệu đề tài. Form giữ dữ liệu khi lỗi, chặn gửi trùng trong lúc chờ và chưa cho gửi khi lựa chọn chưa tải. Sau tạo thành công, popup đóng và danh sách được tải lại. Lỗi tải lại danh sách không làm mất thông báo đã tạo thành công. 401 xóa phiên và quay về đăng nhập; 403 hiển thị lỗi quyền.

Khi POST lỗi mạng/timeout/5xx hoặc 409, frontend không tự gửi lại. Popup khóa dữ liệu và có nút **Kiểm tra kết quả**, gọi `GET /topics/api/v1/topics/{guid}/`: 200 xác nhận đề tài đã tồn tại và tải lại danh sách; 404 cho phép gửi lại thủ công với cùng GUID; lỗi kiểm tra giữ trạng thái chưa xác định. Hủy popup bỏ bản nháp; nếu kết quả gửi chưa rõ, nên kiểm tra trước khi hủy để tránh tạo lại cùng nội dung bằng mã mới. F5 không lưu bản nháp. Đổi trang hủy request frontend đang chờ, nhưng không đảm bảo hủy thao tác backend đã nhận.

Mã nằm trong `features/topics/`: `topic-api.ts`, `useTopics.ts`, `TopicPage.tsx` và các component riêng cho bảng, tìm kiếm, popup. Dùng lại Modal hiện có, bổ sung textarea vào vòng focus bàn phím. Tests dùng API mock kiểm tra payload/GUID, quyền, lỗi, tìm kiếm, cancellation, đường dẫn trực tiếp, F5 và lịch sử điều hướng. Chưa thực hiện tạo đề tài trên tài khoản/backend thật. Các luồng chi tiết, sửa, xóa và quyền role 1/2 được kiểm thử bằng mock API; chưa xác minh trên trình duyệt với backend/tài khoản thật.

### Chi tiết, sửa và xóa đề tài

- **Chi tiết** gọi `GET /topics/api/v1/topics/{id}/`, hiển thị tên, mô tả, ngành, giảng viên, tệp đính kèm (chuỗi, không tự tải), trạng thái và thông tin cập nhật. Trạng thái hiển thị nhãn Chờ duyệt (0), Đã duyệt (1), Mở đăng ký (2), Đóng đăng ký (3); giá trị cũ ngoài danh sách hiển thị Chưa xác định. Lỗi tải có nút thử lại; đóng popup hủy request đọc đang chờ.
- **Sửa** chỉ dành cho admin, lấy dữ liệu mới từ endpoint chi tiết cùng `major_id` và `advisor_id` để điền select đúng theo mã, kể cả trùng/thiếu tên. Giảng viên nhận các ID trong chi tiết đề tài được phân công để xác định quyền chấm điểm. Mã đề tài không đổi. `PATCH` chỉ gửi tên/mô tả/ngành/giảng viên và trạng thái đã thay đổi, giữ nguyên tệp, thời điểm tạo và trường không sửa. Tham chiếu cũ giữ nguyên được chấp nhận dù không còn trong lựa chọn; tham chiếu mới phải hợp lệ. Nếu không đổi gì thì không gửi PATCH.
- **Xóa** yêu cầu **Xác nhận xóa** trước khi gửi `DELETE /topics/api/v1/topics/{id}/`; Hủy không gửi request. 204 đóng popup và tải lại danh sách; 404 thông báo đề tài không còn tồn tại. Xóa đề tài cũng xóa vĩnh viễn toàn bộ đăng ký liên quan, kể cả lịch sử đã hủy. Lỗi 409 hoặc kết quả chưa rõ yêu cầu kiểm tra lại trước khi xác nhận xóa tiếp; đăng ký có thể đã bị xóa dù đề tài còn tồn tại.
- PATCH/DELETE lỗi mạng, timeout hoặc 5xx khóa thao tác ghi và yêu cầu **Kiểm tra kết quả**, không tự gửi lại. Với sửa, GET phải trả đúng các giá trị vừa gửi mới xác nhận dữ liệu; nếu khác, giữ bản nháp và báo cần xem lại. Với xóa, GET 404 xác nhận đề tài đã vắng; GET 200 yêu cầu xác nhận xóa lại thủ công. Lỗi kiểm tra giữ trạng thái chưa xác định. Đây là đối chiếu trạng thái hiện tại, không bảo đảm không có ghi đồng thời hoặc kết quả backend đến muộn.
- Bộ lọc tìm kiếm giữ nguyên sau tải lại thành công. Chặn gửi trùng/đóng popup khi ghi đang chờ; đổi trang hủy request frontend nhưng không bảo đảm hủy xử lý backend. Popup hỗ trợ Escape, vòng focus và khôi phục focus khi phần tử mở còn khả dụng.

## Đăng ký đề tài dành cho sinh viên

Role 3 sử dụng trực tiếp `/student` hoặc menu **Đăng ký đề tài** tại
`/student/registrations`. Hai URL cung cấp cùng giao diện trong dashboard hiện có.
Trang gồm đăng ký hiện tại, danh sách đề tài mở cùng khoa và lịch sử đăng ký.
Các route admin/giảng viên vẫn được bảo vệ theo role; `/admin/registrations` vẫn
là trang đang phát triển.

API đi qua Axios client chung và Gateway với access JWT hiện có:

| Thao tác | Request |
| --- | --- |
| Lịch sử của chính sinh viên | `GET /registrations/api/v1/registrations/` |
| Trạng thái đề tài đang đăng ký | `GET /topics/api/v1/registration-topics/{topic_id}/` |
| Đề tài mở cùng khoa | `GET /registrations/api/v1/available-topics/?after=...` |
| Đăng ký | `POST /registrations/api/v1/registrations/` |
| Hủy đăng ký | `DELETE /registrations/api/v1/registrations/{registration_id}/` |

POST chỉ gửi `topic_id` và `semester` khi sinh viên nhập học kỳ (không bắt buộc,
tối đa 255 ký tự; bỏ khoảng trắng hai đầu). Không gửi student_id, status hoặc
thông tin audit. Đề tài/khoa/trạng thái/quyền sở hữu do backend kiểm tra lại.

- **Đề tài mở:** tìm kiếm theo mã/tên chỉ áp dụng cho các trang đã tải và chỉ chạy
  khi nhấn Tìm kiếm. Nhấn Tải thêm đề tài để tiếp tục theo next_after. Trang rỗng
  nhưng còn cursor vẫn cho phép tải tiếp; lỗi tải thêm giữ lại các trang đã có.
  Tải lại lấy trang đầu và cập nhật lịch sử. Không tự động tải toàn bộ đề tài.
- **Đăng ký hiện tại:** trạng thái 0 là đã hủy; các trạng thái khác, kể cả null,
  được coi là hiện tại theo hợp đồng backend. Có đăng ký hiện tại thì nút đăng ký
  đề tài khác bị khóa. Dữ liệu legacy có nhiều đăng ký hiện tại hiển thị cảnh báo.
  Trang đọc trạng thái đề tài qua Gateway cho từng đề tài hiện tại. Trạng thái 3
  hiển thị thông báo đóng đăng ký và khóa nút hủy. Nếu không xác minh được trạng
  thái, nút hủy vẫn khóa và **Tải lại** sẽ thử đọc lại.
- **Đăng ký/hủy:** có hộp xác nhận hỗ trợ bàn phím, giữ focus và chặn gửi trùng.
  Hủy thành công giữ lịch sử và cho phép chọn lại sau khi xác nhận dữ liệu mới.
  Tên đề tài chỉ được hiển thị khi có trong dữ liệu đã tải; lịch sử luôn dùng mã
  đề tài từ backend, không giả lập tên giảng viên, ngành hoặc thông tin khác.
- **Lịch sử:** lọc Tất cả / Hiện tại / Đã hủy ngay trên dữ liệu lịch sử đã tải.
  Ngày giờ hiển thị theo trình duyệt; metadata null hiển thị dấu gạch ngang.
- **Lỗi:** mã topic_closed, topic_registration_closed, faculty_mismatch, registration_conflict và lỗi dịch vụ
  được chuyển thành thông báo tiếng Việt an toàn. Không hiển thị nội dung lỗi
  nội bộ. HTTP 401 gọi logout hiện có; lỗi tải lịch sử khóa thao tác ghi cho tới
  khi tải lại thành công. Lỗi tải danh sách đề tài mở không chặn xem/hủy đăng ký
  đã xác nhận; lỗi tra cứu trạng thái đề tài hiện tại khóa thao tác hủy.
- **Kết quả chưa rõ:** timeout, mất mạng, phản hồi mutation sai DTO, HTTP 5xx hoặc
  409 yêu cầu nhấn **Kiểm tra kết quả** để tải lại lịch sử, trừ 409
  `topic_registration_closed`: thao tác hủy bị từ chối rõ ràng và trạng thái đề
  tài được đọc lại. Hủy nhận 404 cũng cần
  kiểm tra lại. Khi kiểm tra thất bại, các thao tác ghi vẫn khóa; đóng hộp thoại
  không bỏ khóa này. Không tự động gửi lại POST/DELETE. Kết quả thành công đã xác
  nhận vẫn được giữ khi bước tải lại lịch sử tiếp theo thất bại.
- **Vòng đời:** request dùng AbortSignal; chuyển trang/đăng xuất/hủy request cũ
  không cho phản hồi muộn ghi đè dữ liệu hoặc đăng xuất phiên mới. Khi mở lại
  trang, thao tác ghi chờ lịch sử được tải thành công.

Mã nằm tại `src/features/registrations/`, nối route trong `src/app/App.tsx`.
Không thêm package, thay lockfile, thay backend, schema hoặc môi trường chạy.
Dùng proxy Gateway và cấu hình hiện có. Backend cần được triển khai các hợp đồng
tra cứu academic/topic và cùng JWT_SIGNING_KEY như mô tả trong README service.

Kiểm chứng: `npm run test`, `npm run lint`, `npm run typecheck` và
`npm run build`. Bộ test gồm API adapter, luồng đăng ký và kiểm thử tích hợp
route/session.
Tests dùng jsdom/API mock; chưa kiểm chứng trình duyệt với tài khoản sinh viên và
Gateway/backend thực. CSS có bố cục mobile và bảng cuộn ngang, nhưng chưa kiểm
chứng trực quan trên thiết bị thực.


### Quyền chỉnh trạng thái đề tài

Admin có select trạng thái trong form tạo/sửa: Chờ duyệt (0), Đã duyệt (1),
Mở đăng ký (2), Đóng đăng ký (3); mặc định tạo là 1. Giảng viên không có select này và frontend
không gửi status: backend tạo ở 0 và chặn thao tác đổi trạng thái qua API.
Luồng sinh viên chỉ nhận đề tài status 2 từ API available-topics. Đề tài cũ
status 1 cần admin chủ động mở đăng ký; không tự chuyển dữ liệu hiện có.


### Trạng thái và sinh viên đăng ký trong quản lý đề tài

Bảng đề tài có cột Trạng thái: Chờ duyệt (0), Đã duyệt (1), Mở đăng ký (2), Đóng đăng ký (3);
null/giá trị cũ hiển thị Chưa xác định. Popup Chi tiết của admin/giảng viên
đọc thêm `/registrations/api/v1/topics/{topic_id}/registrations/` để hiển thị
mã sinh viên, họ tên, học kỳ và ngày đăng ký. Chỉ liệt kê đăng ký hiện tại;
đăng ký đã hủy không xuất hiện, trạng thái đăng ký cũ/null có nhãn cần kiểm tra.
Sinh viên không có phần danh sách này và không gọi API quản lý.

Danh sách tải độc lập với chi tiết đề tài, có trạng thái đang tải, rỗng,
lỗi/thử lại và Xem thêm sinh viên cho các trang100 dòng. Nếu tra cứu họ tên lỗi,
vẫn giữ dữ liệu đăng ký theo mã và thông báo chưa đủ họ tên. Đóng popup/đổi trang
hủy request, không cập nhật từ response cũ. Không tải toàn bộ hồ sơ sinh viên,
không gửi lại thao tác ghi, không lộ email/số điện thoại/điểm số.


### Hủy đăng ký sinh viên từ chi tiết đề tài

Chỉ admin có nút **Hủy đăng ký** trên từng dòng sinh viên. Xác nhận
hiển thị họ tên/mã sinh viên; **Quay lại** không gửi request. Xác nhận gửi DELETE
`/registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/`.
Khi thành công, chỉ dòng đăng ký đó được bỏ khỏi danh sách; lịch sử vẫn giữ
ở backend với status0. Các dòng khác và cursor phân trang được giữ nguyên.

Trong lúc gửi, khóa nút xác nhận, đóng popup/Escape và thao tác danh sách để
tránh gửi trùng. Nếu timeout/network/5xx, nút **Kiểm tra kết quả hủy** gọi GET
đúng đăng ký. Chỉ status0 xác nhận đã hủy; nếu vẫn hiện tại, cần xác nhận lại
thủ công. Lỗi kiểm tra giữ trạng thái chưa xác định, không tự gửi DELETE lại.
Đóng popup sau khi request hoàn tất được phép; mở lại đọc danh sách mới. Đổi
trang hủy việc chờ response, không bảo đảm hủy thao tác backend đã nhận.
JWT401 đăng xuất;403 báo không có quyền;404 bỏ dòng đăng ký không còn tồn tại.

### Xóa đề tài kèm đăng ký liên quan

Popup **Xóa đề tài** cảnh báo rằng toàn bộ đăng ký liên quan, kể cả lịch sử đã hủy, sẽ bị xóa vĩnh viễn. Chỉ admin được xác nhận xóa; Hủy không gửi request. Frontend gửi một DELETE đề tài, backend điều phối việc xóa dữ liệu qua regist-service.

Khi lỗi mạng/timeout/5xx hoặc409, popup yêu cầu **Kiểm tra kết quả**, không tự gửi DELETE lại. Thông báo nêu rõ đề tài có thể đã đóng và lịch sử đăng ký có thể đã mất. GET404 xác nhận đề tài hiện không còn; GET200 cho phép xác nhận xóa lại thủ công nhưng không tuyên bố lịch sử đăng ký còn nguyên. Các tests mock kiểm tra cảnh báo, khóa gửi trùng và đối chiếu kết quả; chưa xóa dữ liệu thật để kiểm thử.

### Điểm đăng ký

Sinh viên xem điểm của mình (hoặc “Chưa chấm”) trong đăng ký hiện tại và lịch sử. Admin có thể chấm/sửa điểm của mọi đăng ký còn hiệu lực trong danh sách sinh viên của từng đề tài, kể cả đề tài chưa có giảng viên hướng dẫn. Giảng viên chỉ chấm/sửa điểm thuộc đề tài mình hướng dẫn. Nút chấm/sửa điểm chỉ xuất hiện khi chi tiết đề tài có trạng thái 3; backend kiểm tra lại trạng thái khi nhận PUT và trả 409 `topic_not_closed` nếu đề tài chưa đóng. Điểm từ 0–10, tối đa hai chữ số thập phân. UI gửi một PUT cho mỗi lần xác nhận; nếu kết quả chưa rõ, dùng **Kiểm tra điểm** để đọc đúng giá trị đã lưu trước khi thử lại. Sinh viên tải lại trang để xem điểm vừa được chấm.


## GPA và chỉ tiêu đề tài

Quản lý đề tài có hai ô `GPA yêu cầu` (0–4, mặc định 0) và `Chỉ tiêu sinh viên` (số nguyên dương, mặc định 1); hiển thị trong bảng và chi tiết. Giao diện đăng ký hiển thị GPA yêu cầu cùng số đã đăng ký/chỉ tiêu. Nút đăng ký bị khóa và giải thích khi BE trả `eligible=false`; FE không tự quyết định nghiệp vụ dựa trên GPA do người dùng gửi.

API available-topics bổ sung `req_GPA`, `studentQuota`, `registered_count`, `eligible`, `ineligibility_reason`. Parser từ chối dữ liệu thiếu/sai trường. Khi gửi đăng ký mà BE báo `gpa_requirement_not_met` hoặc `topic_quota_full`, FE hiển thị thông báo tiếng Việt và tải lại eligibility, không tự gửi lại POST. Danh sách chỗ cũng được tải lại sau đăng ký/hủy thành công. Các quy tắc khoa, trạng thái đề tài và một đăng ký hiện tại vẫn được giữ.

Quota storage bound: `studentQuota` is limited to 1–2147483647 (Django integer range); oversized values return validation errors.

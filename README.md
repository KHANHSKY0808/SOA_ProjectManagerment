# Quản lý đồ án tốt nghiệp — SOA

## Yêu cầu môi trường (Requirements)

- Python 3.12 (phiên bản dùng trong CI), Node.js 24 và npm.
- Docker Desktop và Consul đang chạy tại `http://localhost:8500`.
- Có database sẵn: `database/DB_ProjectManagerment.db`.
- Các cổng `5173`, `8000–8004`, `8500` còn trống.

## Swagger / tài liệu API

Sau khi build và chạy API Gateway, mở **http://localhost:8000/swagger/**.
OpenAPI JSON nằm tại **http://localhost:8000/openapi.json**. Tài liệu bao gồm
API auth, academic, đăng ký, đề tài và health qua các prefix gateway hiện có.
Swagger UI và tài liệu được đóng gói cùng gateway, không cần CDN hoặc các
backend đang hoạt động để mở trang tài liệu.

Để thử API, gọi `POST /auth/login/`, sao chép `access`, bấm **Authorize** và
dán token (không thêm chữ `Bearer`). Các quyền admin/giảng viên/sinh viên vẫn
do service kiểm tra. Token không được lưu qua reload; các thao tác tạo, sửa,
xóa chỉ được gửi khi bấm **Try it out → Execute**.

Nếu gateway đã chạy từ image cũ, cần build/recreate riêng gateway để hiển thị
Swagger: từ `api-gateway`, chạy `docker compose up -d --build api-gateway`.
Không cần cài thêm package hoặc khởi động lại các Django service cho thay đổi này.
OpenAPI là file tĩnh: cập nhật cùng thay đổi API và chạy kiểm thử contract;
xem [hướng dẫn bảo trì và kiểm thử](api-gateway/README.md#swagger-and-openapi).

## Cách chạy dự án

Các lệnh dưới đây dùng PowerShell, bắt đầu từ thư mục gốc repository.

### 1. Chuẩn bị backend (lần đầu)

Tạo môi trường riêng, cài requirements và tạo `.env` nếu chưa có:

```powershell
$services = 'auth-service', 'academic-services', 'regist-service', 'topic-service'
foreach ($service in $services) {
    Push-Location "services\$service"
    python -m venv venv
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    if (!(Test-Path .env)) { Copy-Item .env.example .env }
    Pop-Location
}
```

Sửa `.env` của cả bốn backend trước khi chạy:

- Đặt cùng một `JWT_SIGNING_KEY` để phát hành và kiểm tra JWT.
- Access token do auth-service cấp khi đăng nhập hoặc refresh có thời hạn 30 phút. Khởi động lại auth-service để áp dụng; token đã cấp giữ thời điểm hết hạn cũ, thời hạn refresh token không đổi.
- Đặt cùng một `INTERNAL_SERVICE_TOKEN` không rỗng cho các lời gọi nội bộ; dùng giá trị riêng, khác JWT key.
- Đặt `CONSUL_AUTO_REGISTER=true`, `CONSUL_URL=http://localhost:8500`.
- Giữ đúng tên service, port và instance ID riêng trong `.env.example`. Với Docker Desktop, dùng `CONSUL_SERVICE_ADDRESS=host.docker.internal`, health URL tương ứng và cho phép host này trong `ALLOWED_HOSTS`.

Tự tạo các secret thay cho giá trị mẫu; không commit `.env`. Database được ánh xạ theo schema có sẵn, **không chạy migrations để tạo lại bảng nghiệp vụ**.

### 2. Chạy backend và Gateway

Khởi động Docker Desktop và container Consul hiện có. Mở **bốn terminal**, mỗi terminal chạy một dòng dưới đây từ thư mục gốc:

```powershell
# Terminal 1: Auth
& .\services\auth-service\venv\Scripts\python.exe .\services\auth-service\manage.py runserver 0.0.0.0:8001
# Terminal 2: Academic
& .\services\academic-services\venv\Scripts\python.exe .\services\academic-services\manage.py runserver 0.0.0.0:8002
# Terminal 3: Registration
& .\services\regist-service\venv\Scripts\python.exe .\services\regist-service\manage.py runserver 0.0.0.0:8003
# Terminal 4: Topic
& .\services\topic-service\venv\Scripts\python.exe .\services\topic-service\manage.py runserver 0.0.0.0:8004
```

Chờ khoảng 10 giây, mở [Consul UI](http://localhost:8500) và kiểm tra cả bốn service ở trạng thái **Passing**. Sau đó mở terminal khác để chạy Gateway:

```powershell
cd api-gateway
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
```

Compose chỉ khởi động Gateway, dùng Consul có sẵn. Trong container Gateway, `CONSUL_URL` mặc định là `http://host.docker.internal:8500`.

### 3. Chạy frontend

Mở terminal mới từ thư mục gốc:

```powershell
cd fe
npm ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Giữ `VITE_API_BASE_URL=/` và `VITE_API_PROXY_TARGET=http://localhost:8000`. Mở **[http://localhost:5173](http://localhost:5173)**; Vite chuyển tiếp API qua Gateway. Đăng nhập bằng tài khoản đã có trong database.

Kiểm tra nhanh Gateway: [Auth health](http://localhost:8000/auth/health/), [Academic health](http://localhost:8000/academic/health/), [Registration health](http://localhost:8000/registrations/health/), [Topic health](http://localhost:8000/topics/health/).

Nếu gặp `503 Service unavailable`, kiểm tra service đã đăng ký và Passing trong Consul. Nếu lời gọi giữa backend lỗi do Windows không truy cập được `host.docker.internal`, xem cấu hình loopback dành cho local trong README service. Sửa `.env` xong cần khởi động lại service.

## Tóm tắt kiến trúc

Hệ thống dùng SOA: các backend là Django/DRF project độc lập, giao tiếp qua HTTP/REST và JSON. Frontend React gọi API qua Nginx Gateway; Gateway tìm instance khỏe qua Consul và chuyển tiếp JWT. Các service tự kiểm tra JWT và quyền truy cập.

```text
React :5173 -> API Gateway :8000 -> auth-service     :8001
                                -> academic-service :8002
                                -> regist-service   :8003
                                -> topic-service    :8004
                      |
                Consul :8500 (đăng ký / khám phá service)
```

Regist-service gọi academic/topic để kiểm tra sinh viên và đề tài. Topic-service gọi academic để kiểm tra tham chiếu, gọi regist khi xóa các đăng ký liên quan. Academic gọi auth qua API nội bộ khi cần dữ liệu danh tính.

Bốn backend dùng chung file SQLite `database/DB_ProjectManagerment.db`, nhưng mỗi service chỉ truy cập bảng mình sở hữu; tham chiếu liên service dùng ID và REST. Các model database-first dùng `managed = False`. SQLite dùng chung phù hợp cho đồ án, có giới hạn tranh chấp khi ghi đồng thời.

### Chấm điểm đăng ký

Schema `Registrations` có cột `Point` nullable (`NUMERIC`); `NULL` nghĩa là chưa chấm. Khi nâng cấp một database cũ, dừng các service ghi rồi chạy `py database/add_registration_point.py --db database/DB_ProjectManagerment.db --backup D:/backups/registration-before-point.db` từ thư mục gốc. Chọn đường dẫn backup chưa tồn tại và nằm ngoài repository. Script tạo backup nhất quán trước khi thêm cột; không chạy Django migration cho bảng này. Triển khai schema trước khi chạy backend mới. Nếu cần rollback, dừng mọi writer, sao lưu trạng thái hiện tại rồi khôi phục backup; điểm ghi sau thời điểm backup cần được xuất và đối soát riêng.

Admin chấm/sửa điểm cho mọi đăng ký còn hiệu lực. Giảng viên được tạo đề tài Chờ duyệt (0), GVHD tự gán theo user_id trong JWT; giao diện ẩn lựa chọn GVHD. Chỉ Admin duyệt đề tài qua form sửa với đủ trạng thái 0/1/2/3. Giảng viên xem đề tài được phân hướng dẫn, danh sách sinh viên và chấm/sửa điểm; không được sửa, xóa, tự duyệt đề tài hay hủy/xóa đăng ký sinh viên. Quyền được kiểm tra tại API và giao diện dựa trên JWT, không dùng ID do người gọi tự khai báo. Chỉ chấm điểm khi đề tài ở trạng thái 3 (Đóng đăng ký); API trả 409 `topic_not_closed` ở trạng thái khác. Điểm theo thang 0–10 (tối đa hai chữ số thập phân) và được thao tác trong chi tiết đề tài. Sinh viên xem điểm đăng ký của chính mình ở mục hiện tại và lịch sử. API thuộc `regist-service`, tra đề tài qua REST từ `topic-service` và kiểm tra giảng viên hướng dẫn đối với role 2; xem [hợp đồng API](services/regist-service/README.md).

Admin có thể chuyển đề tài sang trạng thái 3 để đóng đăng ký. Đề tài này không xuất hiện trong danh sách đề tài mở (chỉ trạng thái 2); sinh viên đã đăng ký không thể tự hủy. Regist-service xác minh trạng thái đề tài qua REST và trả 409 `topic_registration_closed` nếu sinh viên hủy khi đề tài đã đóng. Trang sinh viên cũng khóa nút hủy sau khi tra cứu trạng thái; backend luôn kiểm tra lại lúc xử lý yêu cầu.

## Các service

| Thành phần | Port / Gateway route | Trách nhiệm và tài liệu |
| --- | --- | --- |
| [auth-service](services/auth-service/README.md) | `8001` · `/auth/*` | Quản lý Users, đăng nhập, phát hành/refresh JWT, hồ sơ hiện tại và API danh tính nội bộ. |
| [academic-service](services/academic-services/README.md) | `8002` · `/academic/*` | Quản lý sinh viên, giảng viên, khoa, ngành và chuyên ngành. Thư mục: `academic-services`. |
| [regist-service](services/regist-service/README.md) | `8003` · `/registrations/*` | Đăng ký/hủy đề tài, lịch sử và kiểm tra điều kiện đăng ký; quản lý đăng ký theo đề tài. |
| [topic-service](services/topic-service/README.md) | `8004` · `/topics/*` | Quản lý đề tài, trạng thái duyệt/mở đăng ký; điều phối xóa đề tài và đăng ký liên quan. |
| [log-service](services/log-services/README.md) | Chưa cấu hình route Gateway | Khung Django tại `log-services`, định hướng ghi audit bất đồng bộ; chưa triển khai pipeline audit, chưa cần chạy cho luồng chính. |
| [API Gateway](api-gateway/README.md) | `8000` | Định tuyến, khám phá instance qua Consul, chuyển tiếp Authorization và request ID. |
| Consul | `8500` | Registry, health check và cung cấp instance khỏe. |
| [Frontend](fe/README.md) | `5173` (dev) | React/Vite/TypeScript, giao diện theo vai trò admin, giảng viên và sinh viên. |

## Lưu ý

- Triển khai hiện tại tách đề tài sang topic-service; các hợp đồng API chi tiết nằm trong README từng service ở bảng trên.
- Auth hiện so sánh mật khẩu plaintext trong database; cơ chế này chưa phù hợp production. JWT vẫn được phát hành và kiểm tra.
- `INTERNAL_SERVICE_TOKEN`, JWT key và Consul ACL token có mục đích riêng; không đưa secret vào frontend hoặc biến `VITE_*`.
- Hướng dẫn trên dành cho local. Production cần HTTPS, cấu hình phục vụ SPA/proxy API và phương án lưu trữ phù hợp.


## Điều kiện GPA và chỉ tiêu đề tài

Topics có thêm `req_GPA` (GPA tối thiểu, 0–4, mặc định 0) và `studentQuota` (số nguyên dương, mặc định 1). Admin nhập/sửa trong quản lý đề tài. Sinh viên chỉ đăng ký mới khi GPA ≥ req_GPA và số sinh viên đang đăng ký < studentQuota, bên cạnh điều kiện khoa, trạng thái mở và một đăng ký hiện tại. Đủ chỉ tiêu thì chặn; đăng ký đã hủy không chiếm suất. Dữ liệu đăng ký cũ được giữ nguyên.

BE lấy GPA từ academic-service và yêu cầu đề tài từ topic-service qua REST; regist-service tự đếm sinh viên trong dữ liệu mình sở hữu và kiểm tra chỉ tiêu trong transaction có khóa ghi SQLite. FE hiển thị yêu cầu/số chỗ và khóa nút theo eligibility do BE trả về. Không đổi service, cổng hoặc gateway prefix.

**Cập nhật schema trước khi chạy mã mới:** dừng các tiến trình ghi database, chạy lệnh bên dưới tại thư mục gốc với một đường dẫn backup mới (không ghi đè). Utility kiểm tra integrity, giữ nguyên dữ liệu/các lỗi FK có sẵn và sao lưu nhất quán bằng SQLite backup API. Chạy lại schema tương thích là no-op; timeout khóa là 3 giây. Không chạy migrate cho bảng unmanaged.

```powershell
& .\services\topic-service\venv\Scripts\python.exe .\database\add_topic_requirements.py --db .\database\DB_ProjectManagerment.db --backup D:\backups\topics-before-requirements.db
```

Utility chỉ thêm hai cột Topics, không thay đổi Students/Registrations. Triển khai schema trước, sau đó phối hợp cập nhật topic/academic/regist và frontend. REST client từ chối dữ liệu thiếu/sai giới hạn với 503. Để rollback: dừng writers, dùng mã trước thay đổi; chỉ khôi phục backup nếu không có dữ liệu mới sẽ bị mất. Không lấy DB từ Git để rollback. Thay đổi GPA/chỉ tiêu trong lúc request đang tra REST không atomic xuyên service; đăng ký cũ không bị hủy khi giảm chỉ tiêu/tăng GPA yêu cầu.

Quota storage bound: `studentQuota` is limited to 1–2147483647 (Django integer range); oversized values return validation errors.

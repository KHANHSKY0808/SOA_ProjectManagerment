# Graduation Project Management System — SOA

## React frontend

The frontend in `fe/` uses React, Vite, TypeScript, and a shared Axios client.
Use Node.js 24 and npm:

```powershell
cd fe
npm ci
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. `VITE_API_BASE_URL` configures the public Gateway
URL (default: `/`). In development, Vite forwards `/auth`, `/academic`,
`/registrations`, and `/topics` to `VITE_API_PROXY_TARGET` (default:
`http://localhost:8000`), preserving paths and Authorization. Browser requests
stay on the frontend origin, so Gateway CORS is not required for this setup.
Use `VITE_API_BASE_URL=/` in `fe/.env` and restart Vite after configuration edits.
In production, serve API routes through the same-origin web server; Vite's dev
proxy is not included in the build. An explicit cross-origin API URL requires
server CORS. Never put secrets in `VITE_*` variables.

Run `npm run lint`, `npm run test`, and `npm run build` inside `fe/`.
Frontend checks run independently in `.github/workflows/frontend-tests.yml`.
Login calls `/auth/login/` using MSSV/UserID and password. Server role 1 routes
to `/admin`, role 2 to `/lecture`, and role 3 to `/student`. Role routes require
an authenticated session and support logout. Nested admin CRUD routes are
`/admin/departments`, `/admin/majors`, `/admin/students`, and `/admin/lecturers`.
Sidebar/shortcut links update the URL, active menu, title and breadcrumb; browser
Back/Forward follows page history. Each role has `/profile` as a development placeholder. `/admin/topics` and `/lecture/topics` provide topic lists, details, creation, editing and confirmed deletion for roles 1 and 2.
Students use `/student` or `/student/registrations` to browse eligible topics,
register, view their history and cancel with confirmation. Admin registration
management remains a development placeholder (see frontend README).
Unknown URLs display 404. Login returns to a known requested route allowed for
the authenticated role; external or unauthorized return destinations are rejected.
Only the access token is saved in tab-scoped sessionStorage; F5 restores a valid
session by validating it through `/auth/me/` before route guards redirect or
render protected pages, preserving the current nested URL. Expired/invalid tokens require login again; transient
restoration failures show retry/return-to-login actions. Logout clears memory
and saved tokens. No password, refresh token or profile persistence, automatic
token refresh, or localStorage is used. Frontend auth tests use mocked API responses;
live Gateway/account integration has not been verified. Production hosting
needs SPA history fallback for nested frontend URLs and unknown frontend paths
while preserving API forwarding. Hosting configuration is not changed by frontend routing.
See [frontend README](fe/README.md)
for structure, error handling, and client usage. Backend ports and routes remain unchanged.

Hệ thống quản lý đồ án tốt nghiệp theo kiến trúc SOA. Mỗi service là một Django
project độc lập, giao tiếp bằng HTTP/REST và JSON.

## Architecture

```text
Client -> API Gateway :8000
           ├─ /auth/*          -> auth-service :8001
           ├─ /academic/*      -> academic-service :8002
           ├─ /registrations/* -> regist-service :8003
           └─ /topics/*        -> topic-service :8004

Consul :8500 supplies healthy instances to the Nginx gateway discovery worker.
```

| Service | Port | Ownership |
| --- | ---: | --- |
| auth-service | 8001 | `Users`, passwords, JWT, current profile |
| academic-service | 8002 | `Faculties`, `Majors`, `Specializations`, `Students`, `Lecturers` |
| regist-service | 8003 | `Registrations` and registration rules |
| topic-service | 8004 | `Topics` and topic lifecycle |
| log-service | — | `AuditLogs` without blocking request paths |
| API Gateway | 8000 | Routing and cross-cutting policy |
| Consul | 8500 | Service registry/discovery |

## Shared database and database-first

Services share the physical SQLite file `database/DB_ProjectManagerment.db`.
This does not share data ownership: a service accesses only the tables it owns,
does not import another service's models, and uses IDs/REST contracts across
boundaries.

The database schema is the source of truth. Django mappings use explicit
`db_table`/`db_column` values with `Meta.managed = False`; schema-altering
migrations require an approved task, backup, and rollback plan.

## Gateway routes

| Prefix | Target |
| --- | --- |
| `/auth/*` | auth-service :8001 |
| `/academic/*` | academic-service :8002 |
| `/registrations/*` | regist-service :8003 |
| `/topics/*` | topic-service :8004 |

The gateway forwards `Authorization: Bearer <token>`. Services validate JWTs
locally with the shared `JWT_SIGNING_KEY` environment value. Authenticated roles
may read academic/topic data. Academic writes require JWT claim `role: 1`; topic writes require integer role 1 or 2, with shared management rights over all topics.

Auth-service login compares passwords directly with plaintext `Users.Password`
values; no password hash verification or database conversion is performed.
This project policy is unsuitable for production because database access exposes
stored passwords. JWT signing and validation remain enabled. See the
[auth-service README](services/auth-service/README.md) for the login contract.

## Repository layout

Academic-service includes `LectureManager` for lecturer CRUD. Its gateway routes
are `/academic/api/lecturers/` (GET/POST) and
`/academic/api/lecturers/{id}/` (GET/PUT/PATCH/DELETE), with string IDs such as
`GV001`. Send a bearer access token: every authenticated role may read, and role
`1` is required to write. DTOs contain `lecturer_id` and nullable `department_id`;
identity data remains owned by auth-service. The app maps the existing Lecturers
table without schema migrations. See the [academic-service README](services/academic-services/README.md)
for examples, status codes and the existing-user-ID requirement.

```text
services/
  auth-service/
  academic-services/
  topic-service/       # topic_manager app
  regist-service/
  log-services/
database/DB_ProjectManagerment.db
api-gateway/
```

## Run services

Use each service's own virtual environment and configure the same
`JWT_SIGNING_KEY` for auth, academic, and topic services.

Auth and academic services automatically load their own `.env` beside `manage.py`
using `python-dotenv`. Install each service's `requirements.txt` in its venv.
Set the same `JWT_SIGNING_KEY` in `services/auth-service/.env` and
`services/academic-services/.env`; process environment values take precedence.
Restart both servers after edits and log in again for a new access token. Missing
files are allowed for deployments that supply environment variables. Regist and topic also load their own local `.env`; log-service retains its
existing environment setup. Do not commit secrets.

```powershell
cd services\auth-service; .\venv\Scripts\python.exe manage.py runserver 8001
cd services\academic-services; .\venv\Scripts\python.exe manage.py runserver 8002
cd services\topic-service; .\venv\Scripts\python.exe manage.py runserver 8004
cd services\regist-service; .\venv\Scripts\python.exe manage.py runserver 8003
```

Topic Service exposes `GET /health/`, `GET /api/topics/`, and protected topic
write endpoints. See [topic-service README](services/topic-service/README.md)
for details.


## Consul-discovered gateway

API Gateway now resolves auth-service, academic-service, regist-service and
topic-service from Consul's passing health instances. It refreshes upstreams
without rebuilding the image; no healthy instance returns JSON 503. The existing
ports/prefixes and forwarded bearer JWT contract remain unchanged. Discovery
uses bounded polling/timeouts and a 15-second default stale-data TTL, after
which routes fail closed on the next polling cycle. Upstream writes are not
retried automatically. Registry failures never enable a static backend fallback.

The Docker Desktop Gateway configuration sets `GATEWAY_UPSTREAM_IP_FAMILY=ipv4`.
Backend hostnames discovered through Consul are resolved to IPv4 literals on
each refresh, avoiding intermittent 503s when `host.docker.internal` also returns
an unreachable IPv6 address. DNS work has a bounded per-service deadline
(`GATEWAY_DNS_TIMEOUT_SECONDS=2`); failures retain only the bounded last-good
discovery cache. No backend IP is hard-coded. IPv6-capable deployments can
explicitly select `auto` mode. Rebuild/recreate only Gateway after changing this
configuration; service ports, prefixes and backend configuration are unchanged.

Configure each backend's local `.env` with `CONSUL_AUTO_REGISTER=true`, a unique
instance ID, reachable address/port and health URL, then start on `0.0.0.0` at
its existing port. Host allowlists include host.docker.internal for Docker health
checks. Auth, academic, regist and topic expose public `/health/`; this reports
liveness, not database readiness. Academic/regist/topic registrations retry in
the background; auth retains its existing startup attempt/manual registration.
All four services now load their own `.env` during settings initialization.

From `api-gateway`, run `docker compose up -d --build` after the existing Consul
container is available at port 8500. Verify service health in the Consul UI.
See [gateway README](api-gateway/README.md) for settings, tests, failure behavior
and Windows/Docker networking. Regist-service's health/registration does not
verify registration business APIs or database readiness. Student registration APIs
are implemented separately as documented below. Database schemas are unchanged.

## Topic CRUD

Topic display names use a separate topic → academic → auth batch lookup chain.
For Windows local services, academic's name client can explicitly use
`AUTH_NAMES_DISCOVERY_ENABLED=false` and
`AUTH_NAMES_BASE_URL=http://127.0.0.1:8001`; this differs from its
`AUTH_IDENTITY_*` management client. Restart academic after environment changes
and ensure auth loaded the same internal credential. Check for older duplicate
runservers still accepting connections if a matching credential returns 403.
Nested lookup delays can exhaust topic's outer timeout and yield null names;
genuinely absent identities or empty names also remain null. See the
[academic name contract](services/academic-services/README.md#topic-display-name-lookup).

If topic creation returns `Academic validation is temporarily unavailable`,
check discovery, topic-to-academic reachability, the forwarded JWT and reference
DTOs. When Django services run on Windows and Consul advertises a Docker-only
address, topic's local `.env` can explicitly use
`ACADEMIC_DISCOVERY_ENABLED=false` and
`ACADEMIC_BASE_URL=http://127.0.0.1:8002`; restart topic-service afterward.
This development setting does not change Gateway/Consul registration or disable
authentication. Deployments should use discovery addresses reachable from each
caller. See [topic reference client](services/topic-service/README.md#academic-reference-client).

Frontend `/admin/topics` and `/lecture/topics` show topic code, name, advisor name and major name, with explicit Search and detail/create/edit/delete actions. Role 1 and 2 share management rights over all topics under the approved policy. Creation uses one GUID per draft (HTTPS/localhost), plus name, description, lecturer and major selects. Editing fetches current reference IDs from management detail and sends only changed fields with PATCH; topic IDs are immutable. Deletion requires confirmation and permanently deletes linked registrations through regist-service before deleting the topic; partial failures require explicit reconciliation. Ambiguous writes require explicit result reconciliation before resubmission: edits compare submitted field values, deletion checks absence. No automatic write retries. See [frontend topic workflow](fe/README.md#danh-sách-và-tạo-đề-tài). Frontend and backend use isolated/mocked tests; live account/browser integration has not been verified.

Topic CRUD supports GET/POST on `/topics/api/v1/topics/` and
GET/PUT/PATCH/DELETE on `/topics/api/v1/topics/{id}/` through the gateway.
Existing `/topics/api/topics/` routes remain available. Authenticated users may
read; integer JWT roles 1 and 2 may create, edit and delete all topics. The existing topic-service:8004 ownership
of Topics is retained as an approved exception to the AGENTS.md diagram.
No database schema, port or gateway prefix changes are required.

Topic writes validate academic references through REST with local JWT checking,
Consul discovery by default, bounded timeouts and a process-local circuit breaker.
Use `ACADEMIC_DISCOVERY_ENABLED=false` with `ACADEMIC_BASE_URL` only for explicit
local development; `ACADEMIC_TIMEOUT_SECONDS` defaults to 2 seconds per call.
Academic major lookup currently accepts numeric IDs only. Responses include
server-controlled audit timestamps and actor. Duplicate/foreign-key conflicts
return 409; dependency/storage failures return 503. See the
[topic-service contract](services/topic-service/README.md#topic-crud-contract)
for JSON examples, PUT/PATCH semantics, settings, errors and verification limits.

Topic responses now return `major_name` and `avisor_name` instead of `major_id`
and `advisor_id` on both existing/v1 routes, including successful write responses.
Write requests still use IDs. This is an approved breaking response change. Management GET detail for roles 1/2 additionally returns raw major_id/advisor_id for edit prefill, preserving display names. List and successful write responses retain the names-only reference DTO; read-only roles receive no extra reference IDs.
Topic calls academic's JWT-protected batch name lookup, which resolves lecturer
names through auth's service-token-protected internal lookup; no cross-service
ORM/table access is used. Configure the same nonempty `INTERNAL_SERVICE_TOKEN`
across trusted services; auth and academic consume it for this lookup. Academic defaults to Consul auth discovery with
`AUTH_NAMES_DISCOVERY_ENABLED=true` and a 2-second per-call
`AUTH_NAMES_TIMEOUT_SECONDS`; explicit `AUTH_NAMES_BASE_URL` applies only with
discovery disabled. Missing credentials/identity names or lookup outages yield
null names while preserving topic read/write response success. See the three
service READMEs for batch limits, quotas, credentials and fallback behavior.

## Student/lecturer accounts and profiles

Admin pages now use `/academic/api/v1/students/` and `/academic/api/v1/lecturers/`
(GET/POST collection; GET/PATCH/DELETE string-ID detail). These composite APIs
manage academic records and nested user fields together. Role is assigned by
server (student 3, lecturer 2); passwords are write-only. Legacy `/api/` academic
routes keep their academic-only behavior for compatibility.

Users remains an auth-service-owned unmanaged mapping. Academic coordinates
through authenticated internal REST; it does not map, join or query Users.
Configure the same nonempty `INTERNAL_SERVICE_TOKEN` in auth and
academic, in addition to the existing shared `JWT_SIGNING_KEY`. Academic resolves
healthy auth instances through Consul by default. No schema/migrations changed.
Restart the two Django services after configuring their environments, and rebuild/
recreate Gateway from its updated config to enforce the internal-route deny.
The internal identity routes are not intended for browser access.

Deletion rejects referenced records and compensates confirmed failures. This is
not a distributed ACID transaction: timeouts, compensation failures and process
crashes can require reconciliation. A 503 `operation_incomplete` requires checking
both records before retrying. See [academic contract and recovery guide](services/academic-services/README.md#composite-studentlecturer-management-v1)
and [auth internal contract](services/auth-service/README.md#internal-identity-management-v1).

## Shared internal-service credential

All five Django services expose the same INTERNAL_SERVICE_TOKEN setting. Use one
nonempty generated environment value across trusted internal callers/providers.
Auth display-name and identity-management endpoints both read it via the existing
X-Service-Token header. Identity management additionally requires the caller's
admin JWT and current admin role. User JWTs/JWT_SIGNING_KEY and CONSUL_TOKEN have
separate purposes and remain unchanged. Public JWT endpoints do not require an
extra internal token; topic currently forwards JWTs to public academic endpoints.

Old per-capability token environment variables are no longer read. Update caller
and provider configuration together and restart affected services. Never expose
the shared secret in VITE variables, source, logs or browser responses. Empty
credentials deny internal access. A shared credential does not identify a unique
calling service; endpoint-specific JWT/role policies still apply. Rotation must
coordinate all internal consumers/providers.

Auth/academic/topic/registration load untracked .env files; log-service reads its
process environment and has no added dotenv dependency. Services with no current
internal endpoint merely expose the common setting; no new routes or automatic
credential forwarding were added.

For Windows local identity development, academic may explicitly set
AUTH_IDENTITY_DISCOVERY_ENABLED=false and AUTH_IDENTITY_BASE_URL=http://127.0.0.1:8001
when Consul's host.docker.internal address is unreachable from Windows. Production
defaults still use discovery; Gateway/Consul registration is not modified.

## Student topic registration APIs

`regist-service:8003` implements registration through Gateway, with locally validated
student access JWTs (integer role 3). Identity comes only from JWT `user_id`.

| Method | Gateway path | Behavior |
| --- | --- | --- |
| POST | `/registrations/api/v1/registrations/` | Register with `{"topic_id":"DT001","semester":"2026-1"}`; semester optional |
| GET | `/registrations/api/v1/available-topics/` | Topic status 2 in the student's faculty; cursor-paginated |
| GET | `/registrations/api/v1/registrations/` | Own registration history; optional `status=active` or `status=cancelled` |
| DELETE | `/registrations/api/v1/registrations/{registration_id}/` | Cancel own registration, preserve history, allow later re-registration |

A student may have at most one current registration across semesters. Eligibility
uses faculty through each major, so different majors in the same faculty are allowed.
Registration status 1 means current, 0 cancelled; other legacy statuses conservatively
count as current. Same-topic/same-semester repeated creation returns the existing
record when current eligibility still passes; other current registrations return 409.

Academic-service provides self student/faculty context and batch major-to-faculty
references; topic-service provides minimal paged open-topic/detail references.
Regist-service resolves both through Consul, forwards JWTs over REST, and only maps
and queries Registrations. Existing topic-service ownership/port/prefix are preserved.
All three need the same `JWT_SIGNING_KEY`. See the [registration service contract](services/regist-service/README.md)
for DTOs, cursor behavior, errors, client timeouts, development URLs and environment.

No schema migration or new dependency is introduced. SQLite serializes the current
registration check and insert across workers; contention returns 503. Eligibility
is a point-in-time REST check, without a distributed transaction. The student frontend
implements this workflow at `/student` and `/student/registrations`. Automated tests use disposable databases and mocked
network calls; live Gateway/Consul integration has not been exercised.

The student page shows current registration, open topics and registration history.
Topic search covers loaded pages; explicit Load More follows the backend cursor,
including filtered empty pages. Register accepts an optional semester. UI actions
require a successfully loaded history and block another registration while a current
one exists, including unknown legacy statuses. Registration/cancellation require
confirmation and never retry automatically. Unknown write results require an explicit
history check before another write is allowed; successful writes remain successful
even when a subsequent refresh fails. Backend authorization and business rules remain
authoritative. See [student frontend workflow](fe/README.md#đăng-ký-đề-tài-dành-cho-sinh-viên).

If the student page receives Gateway `{"detail":"Service unavailable."}`, check
whether `regist-service` has a passing Consul instance. Running Django on 8003
alone does not register it: configure its ignored local `.env` with
`CONSUL_AUTO_REGISTER=true` and the common JWT signing key, then restart that service.
For Windows callers unable to reach Consul's advertised `host.docker.internal`
academic/topic addresses, use explicit local-development loopback client settings;
Gateway discovery remains enabled. See [registration troubleshooting](services/regist-service/README.md#troubleshooting-gateway-service-unavailable).


### Trạng thái đề tài

`0`: Chờ duyệt; `1`: Đã duyệt; `2`: Mở đăng ký. Giảng viên tạo đề tài luôn
ở trạng thái 0 và không được gửi trường status khi tạo/sửa. Admin tạo mặc định
ở trạng thái 1, được chọn 0/1/2 trong form thêm/sửa và qua API. PUT/PATCH không
có status giữ nguyên trạng thái hiện tại. Chỉ đề tài status 2 mới mở cho đăng ký.
Không tự đổi dữ liệu cũ; admin cần chuyển đề tài đã duyệt sang 2 để mở đăng ký.
Trạng thái bản ghi đăng ký vẫn giữ nguyên (1 đang đăng ký, 0 đã hủy).


Khi `available-topics` báo `dependency_unavailable`, kiểm tra cả tên service
trong `/health/`, không chỉ mã HTTP 200. Cổng 8001 phải trả `auth-service`,
8002 phải trả `academic-service`, 8003 trả `regist-service`, 8004 trả
`topic-service`. Chạy `manage.py` từ đúng thư mục service; chạy auth-service
với `runserver 8002` vẫn có health 200 nhưng API học vụ sẽ trả 404.
Mỗi cổng chỉ chạy một service; không khởi động thêm bản trùng khi service đã chạy.


### Danh sách sinh viên đăng ký theo đề tài

Quản lý đề tài hiển thị trạng thái ngay trên bảng. Chi tiết đề tài cho admin
và giảng viên có danh sách sinh viên đang đăng ký (mã, tên, học kỳ, ngày đăng ký),
loại đăng ký đã hủy. API mới: `GET /registrations/api/v1/topics/{id}/registrations/`
với cursor `after` và tối đa100 dòng/trang. Regist-service sở hữu dữ liệu đăng ký,
tra cứu tên bằng `POST /academic/api/v1/student-display-names/`; academic-service
chỉ truy vấn Students và gọi hợp đồng tên nội bộ của auth-service qua REST.
Cả hai API mới yêu cầu JWT role1/2; không thay đổi API đăng ký của sinh viên.
Tên không khả dụng không làm mất danh sách; giao diện báo dữ liệu tên chưa đầy đủ.


Admin và giảng viên có thể hủy đăng ký của từng sinh viên ngay trong Chi tiết
đề tài, có bước xác nhận theo tên/mã sinh viên. API quản lý DELETE
`/registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/`
chỉ chuyển đăng ký sang status0, giữ lịch sử và ghi người thao tác từ JWT.
Backend kiểm tra đúng cặp đề tài/đăng ký và role1/2. GET cùng URL trả trạng thái
chính xác để đối chiếu sau lỗi mạng; frontend không tự gửi lại yêu cầu hủy.

### Xóa đề tài và dữ liệu đăng ký liên quan

Xóa đề tài qua topic-service sẽ đóng đăng ký (status0), yêu cầu regist-service xóa vĩnh viễn toàn bộ đăng ký của đề tài, rồi xóa đề tài. Quyền integer JWT role1/2 giữ nguyên; không xóa sinh viên, giảng viên hoặc người dùng. Regist-service bổ sung DELETE /registrations/api/v1/topics/{topic_id}/registrations/, trả200 với topic_id và deleted_count. Chi tiết timeout/discovery trong README topic-service: REGISTRATION_DISCOVERY_ENABLED (mặc định true), REGISTRATION_BASE_URL (chỉ local development), REGISTRATION_TIMEOUT_SECONDS (mặc định2).

Luồng không có transaction phân tán: nếu bước cuối lỗi, đăng ký có thể đã bị xóa nhưng đề tài vẫn tồn tại và đang đóng. Backend trả503 code deletion_incomplete; UI yêu cầu kiểm tra kết quả rồi xác nhận lại thủ công. Không retry ghi tự động và không thay đổi schema/cổng/prefix. Xem [hợp đồng xóa đề tài](services/topic-service/README.md#cascading-topic-deletion).

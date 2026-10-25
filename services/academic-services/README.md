# Academic Service

Windows: from the repository root, run `start-services.bat` to launch this service
on port 8002 alongside Auth, Registration, Topic and the frontend. Prepare each
service venv/requirements and `.env`, plus frontend dependencies, first.
Use `start-services.bat --dry-run` to check prerequisites without starting servers.
Stop each server with Ctrl+C in its own window. Consul/Gateway run separately;
see the root README for setup and individual startup commands.

Academic Service owns departments, majors, sub-majors, students, and lecturers.
This implementation exposes CRUD APIs for these five resources at port
`8002`. Through the API Gateway, prepend `/academic` to every service path.

## Database boundary

For the current project, academic-service and auth-service use the shared
physical SQLite file `database/DB_ProjectManagerment.db`. This is a project
exception: academic-service owns and accesses only its academic tables; it must
never query or mutate auth-service's `Users` table. SQLite has limited support
for concurrent writers, so production should use separate schemas/credentials
on a server database or separate databases.

## JWT authorization

Set `JWT_SIGNING_KEY` to the exact same secret used by `auth-service`. Do not
commit its real value; use the supplied `.env.example` only as a configuration
template.

Install dependencies using `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.
Settings automatically load this service's `.env` beside `manage.py`, regardless
of the working directory. Existing process environment variables take precedence;
a missing file is allowed. Restart auth and academic servers after editing their
files and log in again. Remove a stale shell key with
`Remove-Item Env:JWT_SIGNING_KEY -ErrorAction SilentlyContinue` before restarting
if you want the file value to take effect. Never commit `.env` or real keys.

Send an access token issued by `auth-service` with every request:

```http
Authorization: Bearer <access-token>
```

For CRUD endpoints, all authenticated roles may use `GET`. `POST`, `PUT`, `PATCH`, and `DELETE`
require the JWT claim `role` to equal the integer `1`.

| Situation | Status |
| --- | ---: |
| Missing, invalid, or expired token | `401` |
| Valid non-role-1 token on a write | `403` |
| Invalid DTO or duplicate field | `400` |
| Unknown resource ID | `404` |

## API endpoints

| Method | Service path | Gateway path | Access |
| --- | --- | --- | --- |
| GET, POST | `/api/departments/` | `/academic/api/departments/` | Read: authenticated; write: role 1 |
| GET, PUT, PATCH, DELETE | `/api/departments/{id}/` | `/academic/api/departments/{id}/` | Read: authenticated; write: role 1 |
| GET, POST | `/api/majors/` | `/academic/api/majors/` | Read: authenticated; write: role 1 |
| GET, PUT, PATCH, DELETE | `/api/majors/{id}/` | `/academic/api/majors/{id}/` | Read: authenticated; write: role 1 |
| GET, POST | `/api/sub-majors/` | `/academic/api/sub-majors/` | Read: authenticated; write: role 1 |
| GET, PUT, PATCH, DELETE | `/api/sub-majors/{id}/` | `/academic/api/sub-majors/{id}/` | Read: authenticated; write: role 1 |
| GET, POST | `/api/students/` | `/academic/api/students/` | Read: authenticated; write: role 1 |
| GET, PUT, PATCH, DELETE | `/api/students/{id}/` | `/academic/api/students/{id}/` | Read: authenticated; write: role 1 |
| GET, POST | `/api/lecturers/` | `/academic/api/lecturers/` | Read: authenticated; write: role 1 |
| GET, PUT, PATCH, DELETE | `/api/lecturers/{id}/` | `/academic/api/lecturers/{id}/` | Read: authenticated; write: role 1 |

## DTOs

All requests and responses use explicit serializers; database models are not
directly serialized.

### Department (`Faculties` table)

Create/update request: `{ "department_id": "F01", "name": "Information Technology" }`

Response: `{ "department_id": "F01", "name": "Information Technology" }`

### Major

Create/update request: `{ "major_id": "KTPM", "name": "Software Engineering", "department_id": "F01" }`

Response includes `major_id`, `name`, and `department_id`.

### Sub-major

Create/update request: `{ "sub_major_id": "WEB", "name": "Web Development", "major_id": "KTPM" }`

Response includes `sub_major_id`, `name`, and `major_id`.

### Student

Create/update request:

```json
{
  "student_id": "SV001",
  "major_id": "KTPM",
  "sub_major_id": "WEB",
  "accumulated_credits": 90,
  "gpa": 3.4
}
```

`sub_major_id` is optional. When present, `sub_major_id` must
belong to the supplied `major_id`.

## Data integrity

### Lecturers (`LectureManager`)

`LectureManager` uses explicit HTTP views, an application service layer, and an
unmanaged model mapping the existing `Lecturers` table. It does not create tables
or require migrations. DTO fields map `lecturer_id` to `LecturerId` and
`department_id` to `FacultyId`. IDs may contain letters, for example `GV001`.

Create request (`POST /api/lecturers/`) and response DTO:

```json
{
  "lecturer_id": "GV001",
  "department_id": "F01"
}
```

`lecturer_id` is required on create and PUT and cannot change on update.
`department_id` is optional and nullable; when supplied, a non-null department
must exist. PATCH preserves omitted fields; `{"department_id": null}` clears the
department. PUT requires `lecturer_id` and preserves an omitted department, in
line with this API's optional-field behavior. No names, email addresses, passwords,
or other auth-owned data are returned. The caller supplies an existing user ID.
This app does not query `Users` or independently verify that ID through an auth
REST contract; the existing database foreign key enforces the reference.

List/retrieve/update return `200`; creation returns `201`; deletion returns `204`
with an empty body. Invalid DTOs, missing departments, duplicate IDs, attempted
ID changes, and database integrity violations return safe field-based `400`
errors. Missing lecturers return `404`. Detail POST returns `405` for authorized
callers. All endpoints require JWT; missing/invalid/expired tokens return `401`,
and authenticated non-role-1 writes return `403`.

Example validation error:

```json
{"department_id": "Department does not exist."}
```

Deletion never cascades into other resources; if the database reports dependent
records, the API returns `400`. Database constraints remain unchanged.

The database hierarchy is `Faculty -> Major -> Specialization`; a Student references a
Major and may reference a SubMajor. Deleting a referenced Department, Major,
or SubMajor is rejected with `400` instead of cascade-deleting academic data.

## Verify

```powershell
cd services\academic-services
..\academic-services\venv\Scripts\python.exe manage.py check
..\academic-services\venv\Scripts\python.exe manage.py test
```


## Gateway service registry integration

The gateway discovers `academic-service` through Consul, rather than a fixed backend URL.
`GET /health/` is public and returns `{"status":"ok","service":"academic-service"}`.
This is a liveness check and does not probe database readiness. JWT authorization
on existing domain endpoints is unchanged.

Settings load this service's `.env` beside `manage.py`; process environment wins.
Install the service's `requirements.txt` in its Python environment. Configure:

```dotenv
CONSUL_AUTO_REGISTER=true
CONSUL_URL=http://localhost:8500
CONSUL_SERVICE_NAME=academic-service
CONSUL_SERVICE_ID=academic-service-8002
CONSUL_SERVICE_ADDRESS=host.docker.internal
CONSUL_SERVICE_PORT=8002
CONSUL_HEALTH_CHECK_URL=http://host.docker.internal:8002/health/
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],host.docker.internal
```

Set `CONSUL_TOKEN` through the environment/file only if registry ACLs require it.
The instance ID must be unique across running instances; change both port and ID
when adding another instance. These address defaults target Django on Windows
and Consul/gateway in Docker Desktop. Use reachable container/service addresses
for a different deployment. Start from this service directory:

```powershell
python manage.py runserver 0.0.0.0:8002
```

Restart after settings/.env changes. Health checks run every 10 seconds with a
2-second timeout and deregister critical instances after one minute. Explicit
commands `python manage.py register_consul` and
`python manage.py register_consul --deregister` update this instance. Admin/test
commands do not register automatically. Keep real secrets out of source control.

Registration runs in a daemon thread without blocking requests. Failed registry
PUTs use 1/2/4/.../30-second backoff, with a 3-second default request timeout.
Successful registrations are refreshed every 30 seconds, recovering from a
registry restart. Set `CONSUL_AUTO_REGISTER=false` (the default) for standalone
commands/development without Consul. No auth-service source imports are used.

## Topic display-name lookup

`POST /api/v1/topic-display-names/` (gateway
`/academic/api/v1/topic-display-names/`) is a read-only batch lookup. All valid
JWT-authenticated readers may call it, including students; it does not apply
CRUD write-role restrictions. The caller JWT is validated locally.

Request and response:

```json
{"major_ids":["1"],"advisor_ids":["GV001"]}
```

```json
{"major_names":{"1":"Information Technology"},"advisor_names":{"GV001":"Nguyen An"}}
```

Both arrays are required and may be empty. Each accepts at most 100 entries,
each a nonblank string <=255 characters; duplicates are removed. The request
must be JSON <=64 KiB, with no unknown fields. ID keys are included even for
missing records, with null values. The batch major lookup accepts TEXT IDs,
including nonnumeric IDs; the existing numeric CRUD detail route is unchanged.
Academic queries only owned Majors/Lecturers and only asks auth about lecturer
IDs that exist in Lecturers, never arbitrary caller-selected user identities.

Configure these environment values (loaded from the service .env, process wins):

```dotenv
# Must match auth-service; use a generated secret, never commit a real value.
INTERNAL_SERVICE_TOKEN=
AUTH_NAMES_DISCOVERY_ENABLED=true
AUTH_NAMES_TIMEOUT_SECONDS=2
# Local development only when discovery is explicitly disabled:
AUTH_NAMES_BASE_URL=http://localhost:8001
```

A nonempty matching token in auth and academic is required for lecturer names.
The service resolves healthy auth-service instances through existing CONSUL_*
settings by default. There is no static fallback. With discovery disabled, the
explicit AUTH_NAMES_BASE_URL is used. The token is sent only as X-Service-Token
to auth's `/internal/v1/user-display-names/`; neither the caller JWT nor Consul
ACL token is sent to that endpoint. Secrets and names are excluded from logs.

For local Windows Django processes, a Docker-advertised auth address such as
`host.docker.internal:8001` may be unreachable from academic even when Consul
marks it healthy. Explicitly configure academic's untracked `.env`:

```dotenv
AUTH_NAMES_DISCOVERY_ENABLED=false
AUTH_NAMES_BASE_URL=http://127.0.0.1:8001
```

These settings affect only display names. `AUTH_IDENTITY_*` controls the separate
identity-management client; changing it does not configure name lookup. Keep
`INTERNAL_SERVICE_TOKEN` consistent with auth and restart academic after editing
its environment. If auth still returns 403 for the matching credential, verify
its running configuration and restart its verified instance after any credential
change. An older duplicate runserver may still accept connections on the same
port: inspect the serving connection's process and service ancestry before
stopping anything. Do not rotate keys or bypass internal authentication to
recover display names.

Topic's outer timeout must allow time for academic's nested auth lookup. If
the inner lookup stalls until the outer timeout, topic cannot use even the major
names from the late batch response. Timeouts bound individual calls, not the
whole chain; fixing a wrong address avoids that delay without guaranteeing names
during future outages. Missing identities or empty stored names legitimately
remain null. Loopback is for services on this host; production discovery
addresses must be reachable from each caller.

Each batch performs at most one discovery GET and one read-only auth POST, with
no retries. AUTH_NAMES_TIMEOUT_SECONDS is finite, >0, <=10 (default 2 seconds
per call); responses are limited to 256 KiB and redirects are rejected. No auth
calls are made when there are no existing advisors. A process-local circuit
opens after three failures for ten seconds. An unavailable/misconfigured auth
lookup, timeout, malformed response or upstream HTTP error retains major names
and returns null advisor names. Full names join trimmed LastName then FirstName;
no available name yields null. Names describe current identities, not snapshots.

Statuses: 200 lookup completed (possibly null names); 400 invalid DTO/body;
401 invalid/missing JWT; 415 unsupported content type; 429 rate limit; 503 local
academic storage unavailable. The endpoint has a 120 requests/minute per-user
throttle using Django's configured cache (default local-memory cache is per
process). Auth applies a shared 120/minute service quota. Topic handles these
lookup failures with null-name fallback. No database schema or ownership changes.
Run `python manage.py check` and `python manage.py test`; lookup tests mock HTTP
and ORM boundaries and do not need running auth/Consul.

## Composite student/lecturer management v1

Admin JWT (role 1) is required for every method, including profile reads.
Gateway adds `/academic` to these service-relative routes:

| Route | Methods | Behavior |
| --- | --- | --- |
| `/api/v1/students/` | GET, POST | List/create student with safe user profile |
| `/api/v1/students/{id}/` | GET, PATCH, DELETE | Read/edit/delete both profile and identity |
| `/api/v1/lecturers/` | GET, POST | List/create lecturer with safe user profile |
| `/api/v1/lecturers/{id}/` | GET, PATCH, DELETE | Read/edit/delete both profile and identity |

POST student example (lecturer substitutes lecturer_id and department_id for the
student academic fields):

```json
{"student_id":"SV001","major_id":"2","sub_major_id":null,"accumulated_credits":0,"gpa":0,"user":{"last_name":"Nguyen","first_name":"An","gender":null,"date_of_birth":"2004-01-31","email":"an@example.com","phone":"0900000000","status":1,"password":"initial-password"}}
```

Example response (POST 201, GET/PATCH 200):

```json
{"student_id":"SV001","major_id":"2","sub_major_id":null,"accumulated_credits":0,"gpa":0,"user":{"user_id":"SV001","last_name":"Nguyen","first_name":"An","gender":null,"date_of_birth":"2004-01-31","email":"an@example.com","phone":"0900000000","status":1,"role":3,"created_at":"2026-10-10T10:00:00+00:00","updated_at":"2026-10-10T10:00:00+00:00"}}
```

Lists return arrays; missing/mismatched legacy identities return user:null rather
than exposing another role's profile. Such rows require reconciliation; PATCH/
DELETE cannot adopt another identity. New IDs are immutable, max255, a single
path segment excluding control characters and `.`/`..`. Email/phone are required
and unique; names nullable/max255, phone max50, email max254, password max1024.
Password is required on create, omitted to preserve on edit; explicit empty
password is rejected. Dates are ISO-8601 YYYY-MM-DD/null. Gender/status are
nullable integers because existing schema defines no enum. Role and timestamps
are response-only. PATCH may include only user fields, only academic fields, or
both; unknown/read-only fields are rejected. Existing local relationship rules
still apply. No undocumented GPA scale or gender/status enum is imposed.

Configure the same `INTERNAL_SERVICE_TOKEN` as auth-service for both identity
management and display-name lookup; never expose it to frontend. Defaults:
`AUTH_IDENTITY_DISCOVERY_ENABLED=true`, `AUTH_IDENTITY_TIMEOUT_SECONDS=2` (>0,
finite, <=10). Only explicitly disabling discovery uses development
`AUTH_IDENTITY_BASE_URL=http://localhost:8001`. Discovery resolves passing
`auth-service` instances using CONSUL_*; no static fallback. Each call performs
at most one discovery GET and one auth request, each with the configured timeout.
No automatic retries. Bodies limited to64KiB, responses256KiB, batches100 IDs;
large lists split into batches. Auth quota120 requests/minute per process cache,
including preflight/compensation calls. Client circuit opens after3 dependency
failures for10 seconds. Redirects, invalid statuses/DTOs and oversized responses
fail closed. Bearer caller JWT, separate X-Service-Token and sanitized shared
X-Request-ID are forwarded; logs omit payloads, tokens, passwords and user IDs.

Statuses: 200 read/edit; 201 created; 204 both deleted; 400 DTO/relationship
validation; 401 invalid JWT; 403 non-admin; 404 missing; 409 duplicate/reference/
concurrent academic change; 415 non-JSON; 503 local/dependency unavailable or
uncertain operation. Identity authorization/rate-limit failures map to safe503.
Field400 errors may be nested under user. A partial/uncertain operation returns:

```json
{"code":"operation_incomplete","detail":"Operation outcome is uncertain. Reload and reconcile academic/identity records before retrying."}
```

Create validates academic inputs, creates identity, then commits child. A local
failure attempts deleting only the newly created identity. Edit validates identity
role, commits academic change, then patches identity; confirmed rejection restores
academic fields only if the snapshot still matches. Delete commits child removal,
then deletes identity; confirmed rejection restores the child. Lost DELETE
responses are resolved with a read, never a repeated DELETE. NO ACTION references
in registrations/topics/audit logs reject deletion; no business/audit cascade.
SQLite transactions cover only owned local writes, never HTTP. Users remains
owned solely by auth; all mappings/schema remain unchanged.

Recovery: stop duplicate attempts for the affected ID; inspect the composite
profile and the authorized internal auth GET through an operator-approved secure
service channel. Check whether both records exist and their intended values.
Never re-create/adopt/delete a pre-existing identity automatically. Repair any
orphan/mismatch through a separately reviewed service-owned operation. Do not
query another service's tables from application code. Process crash recovery is
manual: there is no durable saga journal, broker, distributed lock or ACID promise.
Concurrent edits use academic snapshot comparisons; identity edits are ordinary
last-write-wins. A frontend timeout/unmount can also leave a completed request.

Tests use temporary SQLite and mocked published REST, including references and
compensation; no project DB writes. Run `python manage.py check` and
`python manage.py test`. Legacy academic-only contracts are preserved. Deploy
both services together with matching environment secrets and the updated Gateway
internal-route block; a build alone does not update a running Gateway container.

## Student registration reference contracts

These additive APIs require a bearer access JWT with integer role 3, validated
locally. They never access Users or Topics. Existing CRUD/profile DTOs are unchanged.

- `GET /api/v1/registration-context/`: derives the student from JWT `user_id`
  (including text IDs) and returns `{"student_id":"SV001","department_id":"F1"}`.
  Missing student, major or faculty returns 403.
- `POST /api/v1/major-departments/`: body `{"major_ids":["M1","M2"]}` (maximum
  100 IDs, each at most 255 characters). Returns
  `{"departments":{"M1":"F1","M2":null}}`; missing majors/unassigned faculties
  map to null. No identity/profile data is returned.

Gateway prefix: `/academic`. Invalid input returns 400, invalid JWT 401, wrong
role 403, storage unavailable 503. Callers must fail closed on missing faculty.
Expected usage: one context request and one faculty batch per topic page (100).
No additional endpoint throttle is installed; deployment rate limits belong at
Gateway. Registration clients use a 3-second per-call timeout and no retries.


## Student display names for topic management

`POST /api/v1/student-display-names/` (Gateway `/academic`) is a read-only
batch contract for integer JWT roles1/admin and2/lecturer. Body:
`{"student_ids":["S001","S002"]}`. Up to100 IDs, each at most255 characters,
64KiB request limit, deduplicated; only student_ids is accepted. The lookup uses
only academic-owned Students to select existing student identities before
calling the existing service-authenticated auth name contract. It never reads
Users through the database and returns no profile/contact/grade fields.

Example response:
`{"student_names":{"S001":"Nguyễn An","S002":null},"names_unavailable":true}`.
Unknown students or unavailable/empty names yield null and a true incomplete-name
flag. Empty batches return an empty mapping and false. Auth lookup reuses
IDENTITY_NAMES_CLIENT timeout (default2s), discovery, service token and circuit
fallback; no retries or new configuration. The existing display-name throttle
limits combined lookups to120/min per authenticated identity, per process cache.

Missing/invalid JWT401; role3/other roles403; invalid body400; excessive rate429;
academic storage unavailable503. Identity lookup failure returns200 with null
names so management can still display registration IDs. Consumers must preserve
rows and indicate incomplete names; they must not treat name lookup failure as
an empty roster. Registration ownership and filtering remain in regist-service.

## GPA in registration context

`GET /api/v1/registration-context/` now returns `{"student_id":"SV001","department_id":"F1","gpa":3.2}`. Authentication remains locally validated Bearer JWT, integer student role 3, with identity taken from JWT. This endpoint reads only academic-owned Students/Majors/Faculties; the GPA is not accepted from the caller and not logged. Missing student/faculty returns 403, storage failure 503. Regist-service validates a finite 0?4 GPA and fails safely on missing/malformed values. Existing discovery, bounded client timeout and circuit behavior remain; no additional rate limiter or automatic write retry is introduced. Deploy this additive DTO before enabling the updated registration client. No Students schema change is needed.

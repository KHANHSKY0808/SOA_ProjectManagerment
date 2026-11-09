# Graduation Thesis Management System — SOA

## Prerequisites / System Requirements

- Python 3.12 (version used in CI), Node.js 24, and npm.
- Docker Desktop and Consul running at `http://localhost:8500`.
- Existing SQLite database: `database/DB_ProjectManagerment.db`.
- Available ports: `5173`, `8000–8004`, `8500`.

## Swagger / API Documentation

After building and running the API Gateway, open **http://localhost:8000/swagger/**.
The OpenAPI JSON specification is available at **http://localhost:8000/openapi.json**. The documentation covers Auth, Academic, Registration, Topic, and Health APIs across existing gateway prefixes.
Swagger UI and documentation assets are bundled directly with the gateway; no CDN or active backend services are required to open the documentation page.

To test APIs in Swagger:
1. Call `POST /auth/login/` to authenticate.
2. Copy the `access` token.
3. Click **Authorize** in Swagger UI and paste the token (do not prepend `Bearer`).
Role permissions (Admin / Lecturer / Student) are enforced by individual services. Tokens do not persist across page reloads; create, update, and delete requests are only dispatched when clicking **Try it out → Execute**.

If the gateway was running from an older image, rebuild/recreate the gateway container to serve Swagger:
From `api-gateway`, run: `docker compose up -d --build api-gateway`.
No additional packages or restarts of the Django services are required for this change.
OpenAPI is a static specification file: update it alongside API modifications and run contract tests; see the [maintenance and testing guide](api-gateway/README.md#swagger-and-openapi).

## Getting Started / Running the Project

The commands below use PowerShell, executed from the repository root directory.

### 1. Backend Setup (Initial Run)

Create virtual environments, install dependencies, and create `.env` files if they do not already exist:

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

Configure `.env` for all four backend services before starting:

- Set the identical `JWT_SIGNING_KEY` across services to issue and verify JWTs.
- Access tokens issued by `auth-service` upon login or refresh are valid for 30 minutes. Restart `auth-service` to apply changes; previously issued tokens retain their original expiration, and the refresh token lifespan remains unchanged.
- Set a matching, non-empty `INTERNAL_SERVICE_TOKEN` for internal inter-service calls; use a dedicated secret distinct from the JWT signing key.
- Set `CONSUL_AUTO_REGISTER=true` and `CONSUL_URL=http://localhost:8500`.
- Maintain the service name, port, and unique instance ID defined in `.env.example`. When using Docker Desktop, use `CONSUL_SERVICE_ADDRESS=host.docker.internal`, configure the corresponding health check URL, and include this host in `ALLOWED_HOSTS`.

Generate your own secrets instead of using sample values; never commit `.env` files. The database is mapped to an existing schema: **do not run migrations to recreate business tables**.

### 2. Running Backend Services and API Gateway

**Quick start on Windows:** After preparing the venv/requirements for the four backends, configuring `.env` files, verifying the database, and running `npm ci` in `fe`, open a terminal in the root directory:

```powershell
.\start-services.bat
# To only inspect prerequisites and preview launch commands without starting servers:
.\start-services.bat --dry-run
```

The batch script launches 5 separate command windows: Auth (`8001`), Academic (`8002`), Registration (`8003`), Topic (`8004`), and Frontend (`5173`). You can call the batch file with an absolute path from any directory. The script validates all interpreters, `manage.py` files, Node/npm, and Vite before spawning processes; it does not install dependencies, modify `.env`, or run migrations. Inspect each terminal window's log to verify service readiness or troubleshoot issues. Stop services by pressing `Ctrl+C` in their respective windows and closing them; terminating the launcher window will not terminate the child servers. Do not re-run if ports are already in use. Consul and API Gateway must be started separately as described below; `log-service` is not launched by this script.

Start Docker Desktop and your existing Consul container. Open **four terminal windows**, executing one line in each from the project root:

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

Wait ~10 seconds, then open the [Consul UI](http://localhost:8500) and verify all four services report a **Passing** health status. Next, open another terminal to launch the Gateway:

```powershell
cd api-gateway
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
```

Compose only starts the Gateway, connecting to your existing Consul instance. Within the Gateway container, `CONSUL_URL` defaults to `http://host.docker.internal:8500`.

### 3. Running the Frontend

Open a new terminal from the root directory:

```powershell
cd fe
npm ci
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Keep `VITE_API_BASE_URL=/` and `VITE_API_PROXY_TARGET=http://localhost:8000`. Open **[http://localhost:5173](http://localhost:5173)**; Vite forwards API calls through the Gateway. Sign in using an existing account in the database.

Quick Gateway health checks: [Auth health](http://localhost:8000/auth/health/), [Academic health](http://localhost:8000/academic/health/), [Registration health](http://localhost:8000/registrations/health/), [Topic health](http://localhost:8000/topics/health/).

If you encounter `503 Service Unavailable`, verify that services are registered and Passing in Consul. If inter-service backend calls fail because Windows cannot resolve or route `host.docker.internal`, refer to the local loopback configuration in the respective service README. Restart services after modifying `.env`.

## Architecture Overview

The system follows a Service-Oriented Architecture (SOA): backend services are independent Django/DRF projects communicating via HTTP/REST and JSON. The React frontend accesses APIs through an Nginx API Gateway; the Gateway discovers healthy service instances via Consul and forwards JWTs. Each service independently validates JWTs and enforces authorization.

```text
React :5173 -> API Gateway :8000 -> auth-service     :8001
                                -> academic-service :8002
                                -> regist-service   :8003
                                -> topic-service    :8004
                      |
                Consul :8500 (Service Registration / Discovery)
```

- `regist-service` calls `academic-service` and `topic-service` to validate student status and topic details.
- `topic-service` calls `academic-service` to verify lecturer references, and invokes `regist-service` to remove associated registrations when a topic is deleted.
- `academic-service` calls `auth-service` via internal APIs when identity/user account details are required.

All four backends share the SQLite file `database/DB_ProjectManagerment.db`, but each service strictly accesses only its owned tables; cross-service references use IDs and REST calls. Database-first models declare `managed = False`. A shared SQLite file is suitable for academic projects, with known concurrency limitations on write locks.

### Registration Grading

The `Registrations` schema contains a nullable `Point` column (`NUMERIC`); `NULL` denotes an ungraded registration. When upgrading an older database, stop all writer services and run `py database/add_registration_point.py --db database/DB_ProjectManagerment.db --backup D:/backups/registration-before-point.db` from the root directory. Choose a backup path that does not already exist and is outside the repository. The script creates a consistent backup prior to adding the column; do not run Django migrations for this table. Deploy schema updates before launching newer backends. If a rollback is needed: stop all writers, snapshot the current state, and restore the backup; grades recorded after the backup snapshot must be exported and reconciled separately.

- **Admins** can grade or edit grades for any active registration.
- **Lecturers** create topics in *Pending Approval* state (0); the supervisor (GVHD) is automatically mapped to `user_id` from the JWT, hiding the supervisor selection field in the UI.
- Only **Admins** can approve topics via the **Approve** button in the list when the topic is in state 0, transitioning it to *Approved* (1). The edit form does not present a 0/1 option; once approved, the topic can be set to *Open for Registration* (2) or *Closed for Registration* (3). Content modifications do not automatically change the status.
- Lecturers can view supervised topics, enrolled student rosters, and grade/modify scores; they cannot modify, delete, self-approve topics, or cancel/delete student registrations.
- Permissions are strictly validated on both API and UI layers using JWT claims, never relying on caller-provided identity parameters.
- Grading is only permitted when the topic is in state 3 (*Closed for Registration*); the API returns HTTP 409 `topic_not_closed` otherwise.
- Scores follow a 0–10 scale (up to 2 decimal places) and are managed within the topic detail view.
- Students can view their own registration scores in current and history sections.
- Grading endpoints reside in `regist-service`, querying topic data via REST from `topic-service` and verifying advisor assignment for Role 2 (Lecturer); see the [API Contract](services/regist-service/README.md).

Admins can transition topics to state 3 to close registration. Closed topics no longer appear in the open topic catalog (which only lists state 2); enrolled students cannot unilaterally withdraw. `regist-service` verifies topic status via REST and returns 409 `topic_registration_closed` if a student attempts to cancel after closure. The student UI also disables the cancellation button upon fetching topic state; the backend always revalidates status at request time.

## Admin Registration Management

At `/admin/registrations`, select a topic via the code/title select box to view topic details and enrolled students. The table displays registration ID, student ID, full name, semester, registration date, status, and score, supporting pagination / load more for large cohorts.
Admins can cancel registrations upon confirmation or grade/edit scores (0–10, max two decimal places) once the topic registration is closed (state 3). If write outcomes are ambiguous due to network interruptions, verify the result before repeating actions.
The admin interface reuses existing APIs from `topic-service` and `regist-service` through the Gateway without modifying schemas, ports, or REST contracts.

## Services Overview

| Component | Port / Gateway Route | Responsibilities & Documentation |
| --- | --- | --- |
| [auth-service](services/auth-service/README.md) | `8001` · `/auth/*` | User management, authentication, JWT issue/refresh, current profile, and internal identity API. |
| [academic-service](services/academic-services/README.md) | `8002` · `/academic/*` | Manages students, lecturers, faculties, departments, and majors. Directory: `academic-services`. |
| [regist-service](services/regist-service/README.md) | `8003` · `/registrations/*` | Topic registration/cancellation, history, eligibility checks, and per-topic registration management. |
| [topic-service](services/topic-service/README.md) | `8004` · `/topics/*` | Manages topics, approval/open status lifecycle, topic deletion, and coordinating related registrations cleanup. |
| [log-service](services/log-services/README.md) | Not routed through Gateway | Django framework at `log-services`, intended for asynchronous audit logging; audit pipeline not yet implemented, not required for core flows. |
| [API Gateway](api-gateway/README.md) | `8000` | Routing, Consul instance discovery, forwarding Authorization header and request IDs. |
| Consul | `8500` | Service registry, health checks, and providing healthy backend instances. |
| [Frontend](fe/README.md) | `5173` (dev) | React/Vite/TypeScript, role-based interfaces for Admin, Lecturer, and Student. |

## Important Notes

- Topic management is decoupled into `topic-service`; detailed API contracts can be found in each service's individual README linked above.
- Auth currently compares plaintext passwords against the database; this is intended for academic demo purposes and is not production-grade. JWTs are issued and verified properly.
- `INTERNAL_SERVICE_TOKEN`, JWT signing keys, and Consul ACL tokens serve distinct purposes; never expose backend secrets in frontend code or `VITE_*` environment variables.
- The instructions above are for local development. Production environments require HTTPS, production SPA serving/API reverse proxy configurations, and persistent multi-user database hosting.

## GPA Requirements and Topic Quotas

Topics support `req_GPA` (minimum GPA, 0–4, default 0) and `studentQuota` (positive integer, default 1). Admins configure these fields in topic management. Students can only register if GPA ≥ req_GPA and current enrolled student count < studentQuota, in addition to matching faculty, open registration status (state 2), and having no existing active registration. Once quota is reached, new registrations are blocked; cancelled registrations do not consume quota. Existing registration records remain untouched.

The backend retrieves GPA from `academic-service` and topic prerequisites from `topic-service` via REST; `regist-service` counts current enrollments from its own dataset and enforces the quota within a transaction using SQLite write locking. The frontend displays requirements and available slots, disabling registration buttons based on eligibility returned by the backend. No changes were made to service ports or gateway routing prefixes.

**Update schema before running new code:** Stop database writers and run the command below from the project root with a new backup path (do not overwrite existing backups). The utility performs integrity checks, preserves existing records, and creates a consistent backup using the SQLite backup API. Re-running on compatible schemas is a no-op; the lock timeout is 3 seconds. Do not run migrations on unmanaged tables.

```powershell
& .\services\topic-service\venv\Scripts\python.exe .\database\add_topic_requirements.py --db .\database\DB_ProjectManagerment.db --backup D:\backups\topics-before-requirements.db
```

The migration utility only alters `Topics`, adding two columns without modifying `Students` or `Registrations`. Deploy schema updates first, then coordinate updates across `topic-service`, `academic-service`, `regist-service`, and frontend. REST clients reject missing or invalid out-of-bounds data with HTTP 503. To rollback: stop writer services and revert to the previous codebase; only restore the backup if no newly recorded data would be lost. Do not check out the database file from Git for rollbacks. Concurrent changes to GPA or quota during REST resolution are not cross-service atomic; reducing quotas or increasing GPA requirements will not retroactively cancel existing registrations.

Quota storage bound: `studentQuota` is limited to 1–2147483647 (Django integer range); oversized values return validation errors.

# Registration Service

This service owns the existing `Registrations` table and implements student topic
registration. It reads academic/topic references through REST, validates JWTs
locally, and never queries another service's tables. No schema migration is needed.

## Student registration APIs

All endpoints below require `Authorization: Bearer <access-token>` with integer
JWT `role: 3`. The student ID comes from JWT `user_id`, never client input.
Direct service port is 8003; Gateway strips `/registrations` before forwarding.

| Method | Gateway path | Result |
| --- | --- | --- |
| POST | `/registrations/api/v1/registrations/` | 201 new registration; 200 identical current registration |
| GET | `/registrations/api/v1/available-topics/` | 200 faculty-filtered open-topic page |
| GET | `/registrations/api/v1/registrations/` | 200 own registration history |
| DELETE | `/registrations/api/v1/registrations/{registration_id}/` | 204 cancellation, including repeated cancellation |

Registration request:

```json
{"topic_id":"DT001","semester":"2026-1"}
```

`topic_id` is required; `semester` is optional/nullable. Both are at most 255
characters. Unknown fields (including student_id, status and audit fields) are
rejected. Successful registration response:

```json
{
  "registration_id":"server-generated-uuid",
  "topic_id":"DT001",
  "semester":"2026-1",
  "status":1,
  "created_at":"2026-10-11T03:00:00Z",
  "updated_at":"2026-10-11T03:00:00Z"
}
```

GET registrations returns an array of those DTOs, newest first, restricted to the
caller. Use `?status=active` or `?status=cancelled`; without a filter, both current
and cancelled records are returned. No cross-service lookup is needed to list or
cancel. Another student's registration ID returns the same 404 as an unknown ID.

### Business rules and history

- At most one current registration per student, across all semesters.
- Topic `status` must be exactly integer 1.
- The student's faculty and topic's faculty must exist and match. Faculty is
  resolved from each record's major through academic-service; two different majors
  within the same faculty are allowed.
- Registration status 1 means current; 0 means cancelled. Unknown legacy statuses
  (including null) conservatively count as current. Existing duplicate current
  records produce 409; this service does not silently repair legacy data.
- DELETE changes only registration status, update time and server-derived actor;
  it preserves history. After cancellation, the student may register again.
- Repeating POST with the same current topic and semester returns the existing
  record, provided current academic/topic validation still passes. A different
  topic/semester or multiple current records returns 409. After an ambiguous
  network result, GET registrations to reconcile before trying another write.

Available-topic response:

```json
{
  "results":[{"topic_id":"DT001","name":"SOA","major_id":"M1","status":1}],
  "next_after":null
}
```

Pass a non-null cursor as `?after=<next_after>` (URL-encoded, maximum 255 characters).
Each request examines at most 100 open topics in ascending ID order, then filters
by faculty. A page may have fewer than 100 results or be empty while `next_after`
is non-null: continue until null. The cursor is based on the unfiltered topic page.
The list may still show eligible topics when the student already has a registration;
POST always enforces the single-registration rule. No topic capacity rule is imposed.

### Errors

Errors use `{"code":"stable_code","detail":...}`; detail is a message or field
validation map. For example:

```json
{"code":"faculty_mismatch","detail":{"topic_id":["Topic must belong to the student's faculty."]}}
```

| Status | Meaning / common code |
| --- | --- |
| 400 | Invalid DTO/filter, `topic_closed`, `faculty_mismatch` |
| 401 | Missing, invalid or expired access JWT |
| 403 | Non-student role, missing student or valid faculty (`permission_denied`) |
| 404 | Missing topic, or missing/non-owned registration (`not_found`) |
| 409 | Existing current registration or changed storage references (`registration_conflict`) |
| 503 | Dependency unavailable/malformed (`dependency_unavailable`) or storage lock/failure (`storage_unavailable`) |

Response `X-Request-ID` is forwarded to dependencies. Mutation logs contain only
method, status and sanitized correlation ID; tokens and personal data are excluded.

## Reference clients and environment

Use the same `JWT_SIGNING_KEY` as auth-service, academic-service and topic-service.
The existing Django secret fallback is for development; configure a shared signing
key before using real cross-service tokens. Never commit the actual value.

```dotenv
ACADEMIC_DISCOVERY_ENABLED=true
TOPIC_DISCOVERY_ENABLED=true
ACADEMIC_TIMEOUT_SECONDS=3
TOPIC_TIMEOUT_SECONDS=3
# Optional path override; default is database/DB_ProjectManagerment.db at repo root.
# DATABASE_PATH=D:/SOA_Django/SOA_ProjectManagerment/database/DB_ProjectManagerment.db
```

Discovery resolves passing `academic-service` and `topic-service` instances through
Consul; it does not fall back to static URLs when enabled. Explicit local development:

```dotenv
ACADEMIC_DISCOVERY_ENABLED=false
ACADEMIC_BASE_URL=http://127.0.0.1:8002
TOPIC_DISCOVERY_ENABLED=false
TOPIC_BASE_URL=http://127.0.0.1:8004
```

Restart after environment changes. Each service/registry HTTP call has a default
3-second timeout (configurable, finite, greater than 0 and at most 10). Response
size is bounded to 256 KiB; redirects are denied. Each client opens its failure
circuit after 3 consecutive failures and permits another attempt after 10 seconds.
There are no automatic HTTP retries, including the read-only POST faculty lookup.
JWTs go only to providers; Consul ACL tokens go only to Consul.

POST registration makes one academic context call, one topic detail call and one
academic faculty batch. Available topics use one context, one topic page and at
most one faculty batch of 100 IDs. With discovery enabled, each provider request
also makes a bounded Consul lookup. No extra endpoint rate limiter is installed;
configure deployment request-rate policy at Gateway as needed. Reuse cursors and
avoid repeatedly fetching the same page.

## Storage, verification and limitations

The unmanaged model maps only Registrations; references to other services are
scalar IDs. An SQLite write statement acquires the database writer lock before
checking for current registrations and inserting, within one transaction. This
coordinates concurrent workers; a lock failure returns 503 without a blind retry.
The SQLite lock wait is 3 seconds. Network calls happen before the write lock.
Other writers that bypass this service must enforce the same rule: there is no
database unique index on StudentId and this task adds none.

Cross-service faculty/status validation is point-in-time. A provider may change
data after validation; no distributed transaction or topic reservation is implemented.
This task performs no migrations, production data repair, or broker/event setup.

Run from this service directory using an existing compatible Python environment:

```powershell
python manage.py check
python manage.py test
```

Tests use disposable SQLite tables and mocked network calls, including ownership,
eligibility, history, idempotency, concurrent requests, dependency failures and
circuit recovery. The local verification used `../topic-service/venv/Scripts/python.exe`
because regist-service has no local venv; no dependencies were installed. Live
Gateway/Consul integration was not exercised.


## Gateway service registry integration

The gateway discovers `regist-service` through Consul, rather than a fixed backend URL.
`GET /health/` is public and returns `{"status":"ok","service":"regist-service"}`.
This is a liveness check and does not probe database readiness. JWT authorization
on existing domain endpoints is unchanged.

Settings load this service's `.env` beside `manage.py`; process environment wins.
Install the service's `requirements.txt` in its Python environment. Configure:

```dotenv
CONSUL_AUTO_REGISTER=true
CONSUL_URL=http://localhost:8500
CONSUL_SERVICE_NAME=regist-service
CONSUL_SERVICE_ID=regist-service-8003
CONSUL_SERVICE_ADDRESS=host.docker.internal
CONSUL_SERVICE_PORT=8003
CONSUL_HEALTH_CHECK_URL=http://host.docker.internal:8003/health/
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],host.docker.internal
```

Set `CONSUL_TOKEN` through the environment/file only if registry ACLs require it.
The instance ID must be unique across running instances; change both port and ID
when adding another instance. These address defaults target Django on Windows
and Consul/gateway in Docker Desktop. Use reachable container/service addresses
for a different deployment. Start from this service directory:

```powershell
python manage.py runserver 0.0.0.0:8003
```

Restart after settings/.env changes. Health checks run every 10 seconds with a
2-second timeout and deregister critical instances after one minute. Explicit
commands `python manage.py register_consul` and
`python manage.py register_consul --deregister` update this instance. Admin/test
commands do not register automatically. Keep real secrets out of source control.

### Troubleshooting Gateway "Service unavailable."

If `/student/registrations` receives `{"detail":"Service unavailable."}`, compare
`http://localhost:8000/registrations/health/` with direct
`http://127.0.0.1:8003/health/` and check Consul's passing `regist-service` instances.
A direct 200 with no registered instance makes Gateway return 503 for the entire
`/registrations/` prefix, even though the Django server is running.

This service does not enable registration by default. Ensure the untracked `.env`
beside `manage.py` exists, uses `CONSUL_AUTO_REGISTER=true` with the service/health
settings above, and loads the same `JWT_SIGNING_KEY` as auth/academic/topic. Copy
`.env.example` only when `.env` is absent; never overwrite existing secrets or
generate a different signing key for this consumer. Restart only the affected
service, then wait for its HTTP health check and Gateway discovery refresh.

When Django runs on Windows and Consul/Gateway run in Docker, a healthy advertised
`host.docker.internal` address may still be unreachable from the Windows
registration client. Check it from that caller's network context. For this local
development layout, explicitly set both academic/topic discovery flags to false
and their loopback base URLs as documented above. Gateway continues discovering
regist-service through Consul. Do not use static local development URLs as a
hidden production fallback or disable JWT validation to fix transport errors.

Verification without a token: Gateway registration health should return 200;
protected registration/available-topic requests should return 401 rather than
Gateway 503. This verifies routing and authentication enforcement, not authenticated
student eligibility. Use a legitimate student session for the final read-only
application check; avoid creating/cancelling real registrations for diagnosis.

Registration runs in a daemon thread without blocking requests. Failed registry
PUTs use 1/2/4/.../30-second backoff, with a 3-second default request timeout.
Successful registrations are refreshed every 30 seconds, recovering from a
registry restart. Set `CONSUL_AUTO_REGISTER=false` (the default) for standalone
commands/development without Consul. No auth-service source imports are used.

## Shared internal credential

INTERNAL_SERVICE_TOKEN is the common environment setting across trusted services.
This service currently has no token-authenticated internal contract; the setting
does not introduce endpoints or change public authorization. User JWTs and Consul
ACL credentials remain separate. Never commit a real token or send it to the
frontend. See the root README for coordinated provisioning and rotation.

# Topic Service

Windows: from the repository root, run `start-services.bat` to launch this service
on port 8004 alongside Auth, Academic, Registration and the frontend. Prepare
each service venv/requirements and `.env`, plus frontend dependencies, first.
Use `start-services.bat --dry-run` to check prerequisites without starting servers.
Stop each server with Ctrl+C in its own window. Consul/Gateway run separately;
see the root README for setup and individual startup commands.

`topic-service` owns the existing `Topics` table in the shared project
database. It uses database-first mapping (`managed = False`) and never creates
or migrates that schema.

Run on port `8004` after setting the same `JWT_SIGNING_KEY` as auth-service.

- `GET /health/` is public.
- `GET /api/topics/` requires a valid JWT.
- Topic updates/deletes require integer JWT `role: 1` (admin); role 2 may POST pending topics assigned to themselves. Role 2 lecturers can read only topics assigned to them and grade their students through regist-service.


## Gateway service registry integration

The gateway discovers `topic-service` through Consul, rather than a fixed backend URL.
`GET /health/` is public and returns `{"status":"ok","service":"topic-service"}`.
This is a liveness check and does not probe database readiness. JWT authorization
on existing domain endpoints is unchanged.

Settings load this service's `.env` beside `manage.py`; process environment wins.
Install the service's `requirements.txt` in its Python environment. Configure:

```dotenv
CONSUL_AUTO_REGISTER=true
CONSUL_URL=http://localhost:8500
CONSUL_SERVICE_NAME=topic-service
CONSUL_SERVICE_ID=topic-service-8004
CONSUL_SERVICE_ADDRESS=host.docker.internal
CONSUL_SERVICE_PORT=8004
CONSUL_HEALTH_CHECK_URL=http://host.docker.internal:8004/health/
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],host.docker.internal
```

Set `CONSUL_TOKEN` through the environment/file only if registry ACLs require it.
The instance ID must be unique across running instances; change both port and ID
when adding another instance. These address defaults target Django on Windows
and Consul/gateway in Docker Desktop. Use reachable container/service addresses
for a different deployment. Start from this service directory:

```powershell
python manage.py runserver 0.0.0.0:8004
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

## Topic CRUD contract

This task retains the existing Topics ownership in topic-service on port 8004,
behind gateway `/topics/*`. This is an explicitly approved exception to the root
AGENTS.md diagram that assigns Topics to academic-service. No gateway changes
are required. Academic owns Majors/Lecturers; auth owns Users; regist owns
Registrations. This service queries and mutates only Topics.

| Method | Direct route | Result |
| --- | --- | --- |
| GET | `/api/v1/topics/` | 200 JSON array, ordered by topic_id |
| POST | `/api/v1/topics/` | 201 created topic |
| GET | `/api/v1/topics/{id}/` | 200 topic |
| PUT | `/api/v1/topics/{id}/` | 200 replaced topic |
| PATCH | `/api/v1/topics/{id}/` | 200 partially updated topic |
| DELETE | `/api/v1/topics/{id}/` | 204 empty body |

The existing `/api/topics/` and `/api/topics/{id}/` routes remain aliases.
Gateway examples: `/topics/api/v1/topics/` and `/topics/api/topics/`.
GET requires a valid bearer access JWT. Lecturer role 2 sees only assigned topics, based on JWT `user_id` matching `advisor_id`; details outside that scope return 404. POST permits integer role 1 or 2; lecturer creation forces status 0 and advisor_id equal to JWT user_id before REST reference validation. Only role 1 may PUT/PATCH/DELETE. Students and unknown/string/boolean roles cannot write.
JWTs are validated locally and must include a nonempty string `user_id`.
Health remains public even if a request contains an invalid Authorization header.

POST and PUT request example:

```json
{
  "topic_id": "DT001",
  "name": "Graduation project management with SOA",
  "major_id": "1",
  "advisor_id": "GV001",
  "description": "Independent REST services",
  "file_url": null,
  "status": 1
}
```

`topic_id`, `name`, `major_id` are required for POST/PUT. IDs have a maximum
length of 255; required strings cannot be blank. `topic_id` is immutable; PUT
must include the existing ID. Optional fields except status accept null, and text fields
accept blank strings. Blank advisor_id is normalized to null. Status accepts only JSON integers 0 (pending approval), 1 (approved), 2 (open for registration), or 3 (registration closed); null is rejected. file_url is a
stored string, not an upload or remote fetch. Unknown fields are rejected.
PUT clears omitted optional fields except status; both PUT and PATCH preserve omitted status. For example,
`PATCH /api/v1/topics/DT001/` with `{"name":"Revised title"}` changes only the name
and server audit metadata.

Responses contain seven business fields: `topic_id`, `name`, `description`,
`file_url`, `major_name`, `status`, `avisor_name`, plus read-only `created_at`,
`updated_at` (ISO-8601 UTC), and `updated_by` (validated JWT user_id). Legacy rows
may have null audit values. New rows set both timestamps; updates preserve
created_at. Callers cannot set audit fields. The identity must exist in Users
because the existing database enforces UpdatedBy's foreign key; no auth table
query is performed. JWT validation stays local; optional display-name enrichment
is described below.

| Status | Meaning / example |
| --- | --- |
| 400 | Invalid DTO, changed topic ID, or invalid academic reference; `{"major_id":"Referenced academic record does not exist."}` |
| 401 | Missing, invalid, expired access token or invalid user identity |
| 403 | Caller lacks role 1/2 for POST, or role 1 for PUT/PATCH/DELETE |
| 404 | Topic does not exist; `{"detail":"Topic does not exist."}` |
| 405 | Unsupported method, including POST on detail routes |
| 409 | Duplicate ID or database constraint conflict before registration cleanup |
| 503 | Academic validation or topic storage temporarily unavailable |

Errors use DRF JSON field errors or a `detail` field, without SQL, credentials,
or upstream response bodies. Writes are atomic; failed constraints roll back.
Mutation attempts emit INFO logs with method, status and correlation ID only;
configure application logging to collect them. API responses return X-Request-ID,
preserving a safe incoming ID or generating one. No external log-service calls
block requests. The endpoint does not provide idempotency keys; do not blindly
retry POST. After an ambiguous network failure, GET the client-chosen topic ID.

## Academic reference client

POST/PUT validate major_id and a non-null advisor_id through academic's published
`GET /api/majors/{id}/` and `GET /api/lecturers/{id}/` DTOs. PATCH validates only
supplied references. The caller's bearer header is forwarded; Consul receives
only its own optional ACL token. Cross-service redirects are rejected.

Set `ACADEMIC_DISCOVERY_ENABLED=true` (default) to resolve healthy academic-service
instances from `CONSUL_URL`. There is no static fallback on registry failure.
For local development without Consul, explicitly set it to false and set
`ACADEMIC_BASE_URL=http://localhost:8002`. Registration opt-in and reference
client discovery are independent settings.

### Windows topic process and Docker discovery addresses

If topic-service runs directly on Windows while Consul runs in Docker, a
healthy registered address such as `host.docker.internal:8002` may be reachable
from Docker but unreachable from the Windows topic process. A healthy Consul
check does not establish reachability from every caller. Topic creation then
returns `503 {"detail":"Academic validation is temporarily unavailable."}`.
The same response can also represent discovery failure, academic authorization
failure, timeout, or an invalid academic DTO; first compare the discovered
address with the academic endpoint reachable from the topic host.

For services running together on this Windows host, explicitly configure
topic-service's local, untracked `.env`:

```dotenv
ACADEMIC_DISCOVERY_ENABLED=false
ACADEMIC_BASE_URL=http://127.0.0.1:8002
```

Restart topic-service after editing `.env`; Django's source reloader is not a
reliable way to reload environment files. Keep the existing startup bind address
and port. This setting changes only topic's academic reference/name client.
Consul registration, Gateway discovery, and JWT/reference validation remain
unchanged. Do not use loopback to reach another container or host; deployment
environments should enable discovery with addresses reachable from their callers.
Discovery remains enabled by default in code and has no automatic static fallback.

For `token_not_valid`, check that auth-service and every JWT consumer use the
same `JWT_SIGNING_KEY`, restart any service whose key changed, and use the
login response's access token. `INTERNAL_SERVICE_TOKEN` authenticates internal
contracts and does not replace a user's JWT. Never log tokens or signing keys.
Reference recovery can be verified using read-only major/lecturer detail calls
and the academic client's validation method; creating a real topic is unnecessary.

`ACADEMIC_TIMEOUT_SECONDS=2` bounds each HTTP call (finite, >0 and <=10).
Mandatory write validation performs at most one discovery call plus two academic
GETs, without retries; PATCH without reference fields performs no validation calls.
Optional response name lookups are additional calls described below. Responses are limited to
256 KiB. A process-local circuit opens after three dependency failures for ten
seconds, then allows calls again. Upstream 404 is a 400 field error; upstream
401/403/5xx, malformed DTOs, invalid discovery responses and timeouts become 503
and do not write. Read endpoints retain successful responses with null names during academic outages.
No distributed rate limiter is added; callers should bound concurrent writes.

Current academic major detail routes accept integer IDs despite a TEXT column.
This client rejects nonnumeric major IDs with a clear 400; changing academic's
contract needs a separate approved task. Validation and database writes are not
a distributed transaction: FK enforcement remains the final integrity guard.
Referenced deletion relies on existing SQLite FK constraints and never queries
Registrations. SQLite file contention returns 503; separate databases are needed
for production scaling.

## Verification

From this service's environment:

```powershell
python manage.py check
python manage.py test
```

Tests use Django's disposable SQLite database with explicit unmanaged Topics
schema and minimal foreign-owner fixtures solely for constraint tests. Network
calls are mocked. No schema migrations or production data changes are required;
never point the test database at the shared project file. Existing CI runs both
commands for topic-service. These tests do not verify a running gateway/Consul
or live academic deployment.

## Response names through academic-service

The response now replaces `major_id` with `major_name` and `advisor_id` with
`avisor_name` (this exact spelling is the API field). This is a user-approved
breaking response change on both `/api/topics/` and `/api/v1/topics/`, including
POST/PUT/PATCH responses. Request DTOs and database columns still use IDs. The management-detail exception below adds IDs alongside names only for role 1/2 GET detail; collection and mutation response DTOs stay unchanged.
Update consumers that previously read the two ID response fields.

Example response:

```json
{
  "topic_id": "DT001",
  "name": "Graduation project management with SOA",
  "description": "Independent REST services",
  "file_url": null,
  "major_name": "Information Technology",
  "status": 1,
  "avisor_name": "Nguyen An",
  "created_at": "2026-10-10T08:00:00Z",
  "updated_at": "2026-10-10T08:00:00Z",
  "updated_by": "admin"
}
```

Topic reads only Topics. It deduplicates referenced IDs across the entire response
and calls academic `POST /api/v1/topic-display-names/` with batches of at most 100
major IDs and 100 advisor IDs, forwarding the caller JWT. Academic reads Majors
and Lecturers and obtains lecturer display names through auth's service-token
protected contract. No auth-service code/model is imported by either caller.

Let M and A be distinct major and non-null advisor ID counts. Each enrichment
performs one Consul discovery call (if enabled) and at most ceil(max(M,A)/100)
academic batch calls; an empty list performs none. Each academic batch performs
up to one auth discovery and one auth batch call, only when it contains existing
lecturers. Names are not cached across requests. The response has no per-topic
network lookup. Existing ACADEMIC_* settings apply to lookup transport too.

All network calls are bounded by per-call timeouts, no retries, 256 KiB response
limits and redirect refusal. Display lookup has its own process-local circuit
(three failures, ten-second cooldown), separate from mandatory write validation.
Academic's nested auth lookup has its own equivalent circuit. Each timeout is
per network call, not a total deadline; for large lists callers should bound
concurrency, and nested lookup may exceed the outer timeout and yield null names.
Batch endpoints throttle at 120 requests/minute (academic: per user;
auth: shared academic service quota), using Django's configured cache; default
local-memory throttles are per process, not distributed limits.

An absent advisor, missing identity, or empty identity name returns null. An auth
outage retains major names and returns null advisor names. An academic lookup
failure, invalid DTO, 401/403/429/5xx or timeout returns null names for the topic
response, with a safe warning. No ID is substituted as a fake name. A failed
batch discards that enrichment's names. A completed write keeps its successful
status if optional display lookup fails; mandatory reference validation still
returns 400/503 before writing as documented above.

For lecturer names, configure the same nonempty `INTERNAL_SERVICE_TOKEN`
in auth-service and academic-service through their own environments or local
untracked .env files. Topic-service has the common internal-token setting, but its
current public academic calls forward only the caller JWT. Missing/mismatched
service credentials cause advisor names to be null. See
[academic lookup contract](../academic-services/README.md#topic-display-name-lookup)
and [auth internal contract](../auth-service/README.md#internal-display-name-lookup).

If `major_name` and `avisor_name` unexpectedly become null, check the full
topic → academic → auth lookup chain. Topic's `ACADEMIC_*` configuration and
academic's `AUTH_NAMES_*` configuration are independent. In local Windows
development academic may need `AUTH_NAMES_DISCOVERY_ENABLED=false` and
`AUTH_NAMES_BASE_URL=http://127.0.0.1:8001`, followed by an academic restart.
Changing only `AUTH_IDENTITY_*` does not fix the display-name client.
Auth must also have loaded the matching internal credential; a stale duplicate
runserver can still reject requests after another instance has restarted.

An academic batch may wait on auth longer than topic's outer timeout, causing
topic to discard both names even when academic eventually resolves the major.
Compare read-only batch responses and timing to distinguish this from genuinely
missing identities or empty names. Names remain nullable during outages;
recovering transport/configuration must not manufacture names from IDs.

## Management detail and lecturer permissions

Both existing/v1 aliases allow authenticated integer role 1 (admin) to POST/PUT/PATCH/DELETE topics. Integer role 2 may also POST, forcing status 0 and advisor_id equal to JWT user_id. Lecturer role 2 can list and read only topics whose `advisor_id` equals the JWT `user_id`; other advisors' and unassigned topics are excluded. Detail requests outside that scope return 404. Lecturer PUT/PATCH/DELETE return 403 before mutation or registration cleanup. Query parameters cannot override authenticated ownership. JWTs are validated locally; the server determines the actor from user_id and never trusts a submitted audit field. Academic authorization is unchanged.

`GET /api/v1/topics/{id}/` (also `/api/topics/{id}/`) adds these fields for authorized roles 1/2, alongside all existing display/audit fields:

```json
{ "major_id": "1", "advisor_id": "GV001" }
```

advisor_id may be null. These IDs are topic-owned references, not cross-service ORM lookups. Display names may be null during enrichment outages; raw reference IDs still allow correct edit prefill. Role 3/other read-only callers receive the previous detail DTO. GET collection and POST/PUT/PATCH responses remain unchanged and omit the two reference IDs. Existing callers can continue reading major_name and avisor_name.

The UI uses PATCH for changed name/description/reference fields, preserving untouched fields. Topic ID remains immutable. DELETE returns 204 after removing linked registrations through regist-service; missing topics return 404. Cleanup or subsequent topic deletion failures return safe 503 with code deletion_incomplete. The topic stays closed and registration history may already be permanently removed. No schema, port or package changes are needed; see the cascading deletion contract below.

Callers must not automatically retry writes. After an ambiguous PATCH, GET detail and compare the submitted values, rather than treating existence as proof of update. After ambiguous DELETE, GET 404 means currently absent; GET 200 requires an explicit new confirmation. These are state checks, not a concurrency lock: late requests and other writers can still change the record. Closing or leaving the UI does not roll back a request already accepted by the server.

Tests cover assigned lecturer reads, rejection of other/unassigned detail IDs and lecturer mutations without cleanup side effects, administrator CRUD, role/identity denial, immutable ID, nullable reference details during display outages and unchanged list/mutation DTOs on both API aliases. Use the existing service environment to run manage.py check/test; tests use a disposable database and mock network calls.

## Student registration topic references

These additive endpoints require integer JWT role 3 and preserve existing topic
CRUD DTOs. They query only Topics and return minimal reference metadata:
`{"topic_id":"DT001","name":"SOA","major_id":"M1","status":2}`.

- `GET /api/v1/registration-topics/?after=DT000`: only status 2, ascending topic ID,
  at most 100 records. Response `{"results":[...],"next_after":null}`; a non-null
  cursor continues the next page. Cursor maximum length is 255.
- `GET /api/v1/registration-topics/{topic_id}/`: one topic, including closed topics,
  so registration clients can explicitly reject ineligible status.

Gateway prefix: `/topics`. Invalid query 400, invalid JWT 401, wrong role 403,
missing topic 404, storage unavailable 503. These APIs do not imply eligibility:
regist-service compares faculty via academic-service before writing. Callers use
bounded 3-second requests; no automatic retries. No additional provider throttle
is installed; deployment rate limits can be enforced at Gateway.


## Topic approval and opening registration

JWT role 1 (admin) creates topics with status 1 by default and may explicitly
submit status 0, 1, 2 or 3 on POST/PUT/PATCH. Role 2 (lecturer) may create topics: status is always 0 and advisor_id is JWT user_id, even when omitted or submitted with different valid values. These server-assigned references are validated via academic REST: invalid references return 400 and dependency outages return 503 without writing. Lecturers cannot PUT/PATCH/DELETE or approve topics (403 before request validation).
Malformed or out-of-range status returns 400 for administrators. Omission on PUT or
PATCH preserves the stored status. Other topic management permissions remain unchanged.

For example, admin `PATCH /api/v1/topics/DT001/` with `{"status":2}` opens
registration. Status 1 means approved only: the student registration collection
includes only status 2, and regist-service independently validates that status.
Admin may PATCH status 3 to close registration, then PATCH status 2 to reopen it.
Status 3 remains visible in topic detail and student reference detail, but is
excluded from available topics. Regist-service rejects student self-cancellation
and grading is permitted only while topic status is 3. Existing registration
records and points are not changed by the transition. The detail lookup still
returns closed topics so callers can report ineligibility.
Existing rows, including legacy null statuses, are not rewritten; an admin must
explicitly open approved topics. Existing registration records are unaffected.

## Cascading topic deletion

Both existing topic DELETE aliases require integer JWT role 1/admin. The service first validates topic existence, commits status0 (closed) with server audit metadata, forwards Authorization and a sanitized X-Request-ID to regist-service, then deletes only its own topic. No SQLite write transaction is held during HTTP. Students, lecturers and users are never removed.

Regist-service contract: DELETE /api/v1/topics/{encoded_topic_id}/registrations/ returns200 JSON {"topic_id":"T1","deleted_count":3}, including active, cancelled and legacy-null registration rows. Cleanup is idempotent; it is a permanent purge, unlike individual registration cancellation.

REGISTRATION_DISCOVERY_ENABLED defaults to true: resolve healthy regist-service instances using Consul, with no static fallback on discovery failure. Explicit local development may set REGISTRATION_DISCOVERY_ENABLED=false and REGISTRATION_BASE_URL=http://localhost:8003. REGISTRATION_TIMEOUT_SECONDS defaults to2, must be finite and greater than0 and at most10, and applies separately to discovery and cleanup. There are no automatic write retries or redirects. No new rate limiter is introduced; existing gateway policies apply. Empty or malformed cleanup DTOs, timeout, non200 and dependency failures fail safely.

204 means the topic and linked registrations were removed;404 means topic was already absent before the operation. Before cleanup, storage failures return503 and constraint failures409. After closure, unconfirmed cleanup, concurrent FK references or final storage errors return503 {"code":"deletion_incomplete","detail":"..."}. The topic stays closed if it still exists, and registration history may already be gone. Independent services do not provide a distributed transaction: no automatic compensation or restoration is claimed. An in-flight registration or concurrent topic edit may race; FK enforcement prevents orphan references. Clients must GET the topic after uncertain failure:404 confirms current absence;200 requires a new explicit confirmation and must warn that registration history may already be deleted. Reverting code does not restore deleted data.

Automated tests use disposable databases and mocked HTTP for orchestration, authorization, isolation, rollback, discovery and partial failures. No live registrations are deleted during verification.

## GPA requirement and student quota

`Topics.req_GPA` maps to the unmanaged float field of the same name; `Topics.studentQuota` maps to its unmanaged integer field. Public topic CRUD, management detail and `/api/v1/registration-topics/` list/detail DTOs now include both numeric JSON fields. Admin create/update and lecturer create accept `{"req_GPA":3.25,"studentQuota":2}` alongside existing fields. GPA must be finite, 0?4; quota must be a positive integer. Nulls, booleans, numeric strings and fractional quotas return 400. Omitted create fields default to 0/1; omitted PUT/PATCH fields retain their stored values. Existing authorization and status rules remain unchanged.

Example reference: `{"topic_id":"T1","name":"SOA","major_id":"M1","status":2,"req_GPA":3.25,"studentQuota":2}`. This service owns only Topics and never counts Registrations directly. Registration enforces capacity using its own data. Use `database/add_topic_requirements.py` from the root README to back up and add schema columns before this code starts; do not migrate unmanaged tables. Existing rows default to 0/1 and existing registrations remain valid. Policy edits after registration REST lookup are not atomic across services.

Quota storage bound: `studentQuota` is limited to 1–2147483647 (Django integer range); oversized values return validation errors.

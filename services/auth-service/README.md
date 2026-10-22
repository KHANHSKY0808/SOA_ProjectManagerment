# Auth Service

`auth-service` is the identity provider for the graduation-project management
system. It authenticates records in the existing `Users` table, issues JWTs,
and exposes the authenticated user's safe profile. It does not return a
password in any response.

## Responsibilities

- Authenticate with email or user ID and password.
- Issue and refresh JWT access tokens.
- Return the current authenticated user's profile.
- Register itself in Consul when service discovery is enabled.

The service owns authentication concerns. Other services must not import the
`Users` model or query the auth database directly; they receive a JWT from the
client and validate it, or call auth-service through REST when necessary.

## Run locally

From this directory:

```powershell
..\..\venv\Scripts\python.exe -m pip install -r requirements.txt
..\..\venv\Scripts\python.exe manage.py runserver 8001
```

The direct base URL is `http://localhost:8001`.

When the API Gateway is running, use `http://localhost:8000/auth` instead.
For example, gateway URL `/auth/login/` is forwarded to this service's
`/login/` endpoint.

## API contract

| Method | Service URL | Gateway URL | Authentication | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/health/` | `/auth/health/` | None | Liveness check |
| `POST` | `/login/` | `/auth/login/` | None | Log in and issue tokens |
| `POST` | `/token/refresh/` | `/auth/token/refresh/` | None | Create a new access token |
| `GET` | `/me/` | `/auth/me/` | Bearer access token | Get current user profile |

### `POST /login/`

Access tokens issued by login or refresh are valid for 30 minutes (1800 seconds).
Refresh-token lifetime is unchanged. Restart auth-service to load this setting;
already-issued tokens retain their original expiration.

Request DTO: provide one of `identifier`, `email`, or `userid`, together with
`password`.

```json
{
  "identifier": "sv001@example.com",
  "password": "your-password"
}
```

Successful response (`200 OK`):

```json
{
  "access": "<JWT access token>",
  "refresh": "<JWT refresh token>",
  "token_type": "Bearer",
  "user": {
    "user_id": "SV001",
    "first_name": "An",
    "last_name": "Nguyen",
    "gender": 1,
    "date_of_birth": "2003-01-15",
    "email": "sv001@example.com",
    "phone": "0900000000",
    "role": 1,
    "status": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  }
}
```

Invalid credentials return `401 Unauthorized`. Invalid or missing fields
return `400 Bad Request`.

Login compares the supplied password exactly with the plaintext value in
`Users.Password`, including whitespace and Unicode. It does not verify password
hashes or convert stored values. Accounts containing hashes cannot authenticate
with their original passwords under this policy. Plaintext password storage is
for this project only and is unsuitable for production: database readers can
read every stored password. JWT signing and bearer authentication are unchanged.

### `POST /token/refresh/`

Request DTO:

```json
{
  "refresh": "<JWT refresh token>"
}
```

Successful response:

```json
{
  "access": "<new JWT access token>",
  "token_type": "Bearer"
}
```

### `GET /me/`

Send the access token:

```http
Authorization: Bearer <JWT access token>
```

The response is the `user` DTO shown in the login response. The `password`
column is never serialized.

## JWT and other services

The login token includes `user_id`, `email`, and `role` claims. Academic and
registration services should validate its signature and expiration locally,
then use those claims for authorization. They should not call `/me/` for every
request.

For the current Django setup, configure the same explicit JWT signing key (or
preferably an auth-service private key and a public key in consuming services)
before sharing tokens across services. Do not rely on each service's separate
Django `SECRET_KEY` and do not commit the signing key to Git.

## Consul service registration

The service has a public `GET /health/` endpoint. When
`CONSUL_AUTO_REGISTER=true`, it registers an `auth-service` instance at
startup. Consul checks the health endpoint every 10 seconds and deregisters an
instance after one minute of failed checks.

Start a local Consul development agent:

```powershell
docker run --rm --name soa-consul -p 8500:8500 hashicorp/consul agent -dev -client=0.0.0.0
```

In another PowerShell window, enable registration and run auth-service. The
following address is correct when Django runs on Windows and Consul runs in a
Docker container:

```powershell
$env:CONSUL_AUTO_REGISTER = "true"
$env:CONSUL_SERVICE_ADDRESS = "host.docker.internal"
$env:CONSUL_HEALTH_CHECK_URL = "http://host.docker.internal:8001/health/"
..\..\venv\Scripts\python.exe manage.py runserver 8001
```

Open `http://localhost:8500` and verify that `auth-service` is healthy.

For a one-off operation:

```powershell
..\..\venv\Scripts\python.exe manage.py register_consul
..\..\venv\Scripts\python.exe manage.py register_consul --deregister
```

Configuration keys and defaults are in [.env.example](.env.example). Install
dependencies with `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.
Settings automatically load `.env` beside this service's `manage.py`, regardless
of the working directory, before reading JWT and Consul configuration. Existing
process environment variables take precedence over file values. A missing file
is allowed; do not commit real secrets. Use the same `JWT_SIGNING_KEY` in auth
and academic services. Restart both servers after changing `.env`, then log in
again to get a token signed with the current key. If an old shell value remains,
remove it with `Remove-Item Env:JWT_SIGNING_KEY -ErrorAction SilentlyContinue`
before restarting. `CONSUL_AUTO_REGISTER=true` in `.env` enables registration
on startup and requires the configured Consul instance to be available.

## Verification

```powershell
..\..\venv\Scripts\python.exe manage.py check
..\..\venv\Scripts\python.exe manage.py test authentication
```


## Gateway service registry integration

The gateway discovers `auth-service` through Consul, rather than a fixed backend URL.
`GET /health/` is public and returns `{"status":"ok","service":"auth-service"}`.
This is a liveness check and does not probe database readiness. JWT authorization
on existing domain endpoints is unchanged.

Settings load this service's `.env` beside `manage.py`; process environment wins.
Install the service's `requirements.txt` in its Python environment. Configure:

```dotenv
CONSUL_AUTO_REGISTER=true
CONSUL_URL=http://localhost:8500
CONSUL_SERVICE_NAME=auth-service
CONSUL_SERVICE_ID=auth-service-8001
CONSUL_SERVICE_ADDRESS=host.docker.internal
CONSUL_SERVICE_PORT=8001
CONSUL_HEALTH_CHECK_URL=http://host.docker.internal:8001/health/
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],host.docker.internal
```

Set `CONSUL_TOKEN` through the environment/file only if registry ACLs require it.
The instance ID must be unique across running instances; change both port and ID
when adding another instance. These address defaults target Django on Windows
and Consul/gateway in Docker Desktop. Use reachable container/service addresses
for a different deployment. Start from this service directory:

```powershell
python manage.py runserver 0.0.0.0:8001
```

Restart after settings/.env changes. Health checks run every 10 seconds with a
2-second timeout and deregister critical instances after one minute. Explicit
commands `python manage.py register_consul` and
`python manage.py register_consul --deregister` update this instance. Admin/test
commands do not register automatically. Keep real secrets out of source control.

Existing auth automatic registration makes a background attempt at startup;
it does not have periodic retry. If Consul was unavailable or restarted, run
`python manage.py register_consul` again after it is available.

## Internal display-name lookup

`POST /internal/v1/user-display-names/` supplies current lecturer identity names
to academic-service. This is an internal read-only contract, authenticated with
a dedicated X-Service-Token header. Ordinary user JWTs alone cannot access it.
A missing/empty configured token denies every request. Set the same generated
nonempty `INTERNAL_SERVICE_TOKEN` environment value in auth and academic;
never put it in frontend variables, repository files or client responses. Use
private networking/TLS for this service credential outside local development.
Existing login, refresh, health and me contracts remain unchanged.

Request DTO (JSON <=64 KiB):

```json
{"user_ids":["GV001","missing"]}
```

Response DTO:

```json
{"names":{"GV001":"Nguyen An","missing":null}}
```

Only user_ids is accepted, with at most 100 nonblank string entries of at most
255 characters; duplicates are removed and empty arrays are valid. Auth queries
only Users and selects UserId, LastName and FirstName, joining trimmed LastName
then FirstName with a space. Missing users or empty name parts yield null.
No password, phone, email or other profile fields are returned. No schema change
or public arbitrary-user profile endpoint is introduced. The gateway may route
the path through its existing auth prefix, but service-token authentication is
always required; do not distribute the token to end users.

Statuses: 200 lookup; 400 invalid input/body; 403 missing/invalid service token;
415 unsupported content type; 429 quota exceeded; 503 identity storage unavailable.
The endpoint uses a shared academic-service quota of 120 requests/minute through
Django's configured cache; the default local-memory cache limits each process
independently. Caller timeout is bounded by academic's AUTH_NAMES_TIMEOUT_SECONDS,
2 seconds per call by default, and callers do not retry automatically. Academic
uses nullable name fallback on dependency failures. No external services are
called by this endpoint. Run `python manage.py check` and `python manage.py test`
for contract, permission, size-limit, quota and safe-error coverage.

## Internal identity management v1

Auth alone owns Users, mapped unmanaged to the existing table. This task creates
no tables or migrations. Public login/refresh/me contracts and the existing
password comparison policy are unchanged.

Internal callers must send BOTH `X-Service-Token` matching a nonempty
`INTERNAL_SERVICE_TOKEN` and `Authorization: Bearer <admin-access>`.
The JWT role and current database user role must both be1. Both internal identity
management and display-name lookup use the same shared credential. Provision it through environment/
untracked .env identically in academic; never put it in VITE/browser variables.
Gateway returns404 for `/auth/internal` and all `/auth/internal/*` paths, including
encoded forms after Nginx normalization. Protect the auth-service port with
network access policy in deployments; direct calls still require both credentials.

| Internal route | Methods |
| --- | --- |
| `/internal/v1/identities/{kind}/` | POST |
| `/internal/v1/identities/{kind}/{user_id}/` | GET, PATCH, DELETE |
| `/internal/v1/identity-profiles/{kind}/` | POST read-only batch |

kind is students or lecturers, assigning roles3/2 respectively. POST receives
user_id, email, phone, password, optional last_name/first_name/gender/date_of_birth/
status. PATCH accepts only supplied mutable fields; user_id is immutable.
Unknown fields, role and timestamps are rejected. Password required create,
omitted edit means unchanged, empty rejected; exact Unicode/whitespace comparison
policy is preserved. Dates YYYY-MM-DD/null, gender/status nullable integers with
no schema-defined enum, names max255 nullable, email max254, phone max50, password
max1024; ID max255 single path segment, excluding control chars and `.`/`..`.
Unique ID/email/phone is enforced by SQLite. CreatedAt/UpdatedAt generated as
ISO-8601 timestamps. Cannot access/delete caller, admins or wrong-role identity.

Safe responses use the public profile DTO fields only: user_id, last_name,
first_name, gender, date_of_birth, email, phone, role, status, created_at, updated_at.
Passwords never appear. POST201, GET/PATCH200, DELETE204, invalid DTO400,
unauthenticated401, forbidden403, absent404, unique/reference conflict409,
unsupported media415, throttle429, storage unavailable503. Errors contain safe
detail/field messages, excluding database internals. No cascades across owned
boundaries: external NO ACTION references prevent deleting Users.

Batch request `{"user_ids":["SV001","missing"]}` ->
`{"users":{"SV001":{...safe profile...},"missing":null}}`. Returns null for
missing/wrong-role users, never discloses other capabilities. Max100 IDs, each
max255, JSON body64KiB. Per-process cache quota120 requests/minute for this
internal capability, including CRUD and batch calls. Correlation X-Request-ID is
sanitized/generated, returned and logged with method/kind/status only; credentials
and personal payloads excluded. No retry of writes; academic uses finite
per-call timeouts (default2s) and explicit compensation, see
[composite workflow/recovery](../academic-services/README.md#composite-studentlecturer-management-v1).

Run `python manage.py check` and `python manage.py test`. Identity lifecycle tests
use isolated SQLite, including synthetic external references, authorization,
unique constraints, safe DTOs and compatibility with login. They never modify
real user data. Restart auth/academic after provisioning the matching secret.

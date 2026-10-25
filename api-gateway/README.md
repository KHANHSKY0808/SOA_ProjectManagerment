# API Gateway with Consul discovery

Nginx listens on port `8000`. A Python standard-library worker queries Consul
`GET /v1/health/service/{name}?passing=true`, validates addresses/ports and renders
Nginx upstreams from healthy instances. Backend addresses are not fixed in the
image. Service addresses fall back to the Consul node address only when the
registered service address is empty. Address-family handling is configurable;
the Docker Desktop Compose setup selects IPv4 to avoid unreachable IPv6 host
addresses. Automatic mode retains IPv4, IPv6 and DNS hostname support.

| Gateway prefix | Consul service name | Prefix forwarded |
| --- | --- | --- |
| `/auth/` | `auth-service` | `/` |
| `/academic/` | `academic-service` | `/` |
| `/registrations/` | `regist-service` | `/` |
| `/topics/` | `topic-service` | `/` |

For example, `/academic/api/lecturers/?page=2` becomes `/api/lecturers/?page=2`.
Authorization and forwarding headers are preserved; a gateway-generated
`X-Request-ID` is forwarded. Services remain responsible for JWT and role checks.
Gateway code contains no domain models or business rules. Access logs exclude
Authorization, request bodies and query strings. CORS is not implemented here.

## Run on Windows with Docker Desktop

1. Start Docker Desktop and the existing Consul container at port `8500`.
2. Configure each backend's `.env` using its `.env.example`. Set
   `CONSUL_AUTO_REGISTER=true`; use a unique `CONSUL_SERVICE_ID` per instance.
   Keep the same JWT signing key for auth, academic and topic.
3. Run each Django server on its assigned port, bound to `0.0.0.0`, for example:

```powershell
cd services\academic-services
.\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8002
```

Use ports 8001/8003/8004 in auth/regist/topic respectively. Regist currently uses
an available project Python environment if it has no service-local venv.
`ALLOWED_HOSTS` must include `host.docker.internal` and the host sent by clients.
The local defaults include localhost, loopback and host.docker.internal.

4. Open http://localhost:8500 and confirm the instances are Passing. Only healthy
   registered instances can receive gateway traffic. After starting a service,
   allow a health-check interval (10 seconds). Existing auth registration can be
   retriggered using `python manage.py register_consul` if necessary.
5. From `api-gateway`, optionally copy `.env.example` to `.env` and build/start:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 30
docker compose exec -T api-gateway nginx -t
```

Compose reads its own `.env`. Inside the gateway container, Consul's URL is
`http://host.docker.internal:8500`; backend Django uses `http://localhost:8500`
when running on Windows. Do not use container-local localhost for a host registry.
This setup reuses the existing Consul instance; Compose does not start another.

## Configuration and failures

| Variable | Default | Meaning |
| --- | --- | --- |
| `CONSUL_URL` | `http://host.docker.internal:8500` | Registry HTTP(S) endpoint |
| `CONSUL_TOKEN` | empty | Optional ACL token, never logged |
| `CONSUL_REFRESH_SECONDS` | `3` | Refresh interval after each polling cycle |
| `CONSUL_TIMEOUT_SECONDS` | `2` | Per-registry-request socket timeout |
| `CONSUL_STALE_TTL_SECONDS` | `15` | Maximum age for cached discovery data |
| `GATEWAY_UPSTREAM_IP_FAMILY` | `ipv4` in Compose; `auto` for standalone worker | Backend address mode: `ipv4` or `auto` |
| `GATEWAY_DNS_TIMEOUT_SECONDS` | `2` | Total DNS child-process time limit per service lookup; finite, >0 and <=10 seconds |

In `ipv4` mode, Consul-provided hostnames are resolved to IPv4 literals before
rendering Nginx upstreams. Literal IPv4 addresses pass through; IPv6-only
instances are excluded. No host IP is hard-coded. Hostnames are deduplicated
within each service lookup and resolved again during each discovery refresh,
so changes to their IPv4 addresses can update routes without a container
restart. Each service's hostname batch uses one short-lived Python process;
the parent kills and reaps it on timeout, preventing abandoned DNS threads.
No resolver subprocess is needed for literal addresses. The DNS deadline is
additional to the Consul request timeout; four service lookups remain concurrent.

DNS failures, missing IPv4 results and DNS timeouts use the existing last-good
discovery cache only until its stale TTL expires; they never fall back to IPv6
or a static service address. A successful lookup with only IPv6 literal
instances yields no upstream immediately. Invalid address-family settings stop
startup. Use `GATEWAY_UPSTREAM_IP_FAMILY=auto` for deployments that support IPv6;
in that mode Nginx resolves backend hostnames with its existing behavior and the
worker's IPv4 DNS deadline is not used.

Docker Desktop may return both A and AAAA records for `host.docker.internal`
even when the Gateway container cannot reach the IPv6 address. Previously this
could produce intermittent `Network unreachable` errors and JSON 503 responses
while Consul still marked the service Passing. Compose's IPv4 mode avoids that
unreachable address without enabling request retries. After changing these
settings or the worker code, recreate Gateway with `docker compose up -d --build
api-gateway`; restarting backend services or Consul is not required.

The four services are queried concurrently. Startup works without Consul and
returns JSON `503` for unavailable service routes. A successful empty lookup
removes its upstream immediately. On lookup failure, last good instances are
used only while younger than the stale TTL. Expiration takes effect on the next
poll; detection includes the poll interval and lookup timeout. This is bounded
polling, not immediate health push. Unknown paths return JSON `404`.

Multiple healthy instances use Nginx round-robin balancing. Candidate configs are
checked with `nginx -t`; only changed, valid configs are replaced and reloaded.
A failed config validation/reload terminates the supervised process/container
instead of indefinitely keeping stale routes; Compose restarts it with a safe
bootstrap. Nginx gets graceful shutdown (up to 12 seconds) before forceful exit.
Worker and Nginx are supervised together; an unexpected Nginx exit also ends the
container. In-flight requests may finish during a normal reload.

Proxy connect timeout is 2 seconds; read/send inactivity timeouts are 10 seconds.
Automatic upstream retries are disabled for all methods, including writes.
Connection/timeout errors return a safe JSON `503`. A live backend can still
return application `4xx` responses; registration does not implement domain APIs.
In particular, regist-service currently has health/registry plumbing but no
registration business API. Services keep their own data ownership.

## Verification

```powershell
python -m unittest discover -s tests -p 'test_*.py'
docker compose config --quiet
docker compose build
docker run --rm --mount "type=bind,source=$($PWD.Path)\tests,target=/tests,readonly" --entrypoint python3 soa-api-gateway:local /tests/integration.py
```

Integration tests run mock registry/backends inside a disposable container,
without contacting the real Consul, Django servers or project database. They
exercise actual Nginx reloads, changing instance ports, balancing, JWT/header and
query forwarding, unavailable services, registry outage/recovery, dual-stack
hostnames with unreachable IPv6, IPv6-only instances and no write replay. The
dual-stack test makes 40 repeated GETs through the real Nginx instance and
asserts IPv4 literals in the generated upstream configuration. CI runs these
checks in `.github/workflows/python-tests.yml`.

Use `docker compose stop` to stop this gateway only. No volume or database
cleanup is required. Production Consul deployment must supply its own security,
durable state and routing/host configuration; the local Consul dev container is
not a production cluster.

References: [Consul health service API](https://developer.hashicorp.com/consul/api-docs/health),
[Nginx proxy retry policy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream).

## Internal auth route policy

Both bootstrap and discovered Nginx configurations return404 for
`/auth/internal` and `/auth/internal/*` before public `/auth/` forwarding. This
blocks internal identity-management and display-name contracts from browser
routing, including encoded paths normalized by Nginx. Direct internal callers
resolve auth-service via Consul and authenticate there; Gateway does not own
identity business logic. Public login/refresh/me forwarding is unchanged.
Rebuild/recreate Gateway when deploying this policy; building the image alone
leaves existing containers running their old configuration. Unit and isolated
real-Nginx integration tests exercise the deny with public routing regressions.

## Swagger and OpenAPI

Open **http://localhost:8000/swagger/** for Swagger UI, or
**http://localhost:8000/openapi.json** for the OpenAPI 3.0.3 document. Swagger UI
5.33.1 JS/CSS and its license are vendored under `docs/vendor/`; their official
release URLs and SHA-256 hashes are recorded in `manifest.json`. No CDN or remote
schema validator is contacted at page load. The UI sets `validatorUrl: null`,
`persistAuthorization: false`, and `queryConfigEnabled: false` using the
[official Swagger UI configuration](https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/).

The static specification documents 38 paths and 75 operations across auth,
academic (including legacy and composite profile endpoints), topics (both
aliases), registrations, and gateway/service health. Log-service currently has
no public business API or gateway prefix, so none is invented here. Internal
auth contracts and Django admin pages are excluded. Documentation introduces no
Django imports, schema introspection, database access, or runtime dependencies
in any service. `nginx-docs.conf` is included by both the bootstrap configuration
and discovery-generated configurations, so documentation survives discovery
reloads and backend/Consul outages.

The OpenAPI server URL `/` targets the gateway origin serving this page. Obtain
an access token from `POST /auth/login/`, click **Authorize**, and paste only the
access token; Swagger adds the `Bearer` prefix. A refresh token is not an access
token. Authorization stays in memory and is cleared on page reload. The UI
does not execute operations automatically. **Try it out → Execute** uses the
existing endpoints, including real writes if selected. Service role/ownership
checks apply exactly as they do for the frontend. A 503 from an API dependency
does not prevent browsing documentation and does not imply an uncertain write
can be safely replayed.

Deployment: rebuild/recreate only the gateway from its directory:

```powershell
docker compose up -d --build api-gateway
```

No Django package install, migration, backend restart, new service, or port
change is needed. Existing containers retain their previous files until
recreated. For a separate, disposable verification image without replacing the
running gateway:

```powershell
docker compose config --quiet
docker build -t soa-api-gateway:swagger-test .
docker run --rm --entrypoint nginx soa-api-gateway:swagger-test -t
docker run --rm --mount "type=bind,source=$($PWD.Path)\tests,target=/tests,readonly" --entrypoint python3 soa-api-gateway:swagger-test /tests/integration.py
```

Maintain `docs/openapi.json` in the same task as route/DTO changes. It is a static
contract, not a runtime-generated schema. `tests/test_openapi.py` checks published
route/method coverage against service URL/view source, inherited DTO field
coverage, local references, operation IDs, security declarations, partial update
schemas, UI configuration, and vendored asset hashes without importing Django
or querying a database. It does not prove all business rules or DTO constraints
match; review those descriptions alongside affected service tests. The
OpenAPI validator is test-only and is never installed into service environments
or the gateway image. From the repository root, use an isolated tooling venv:

```powershell
python -m venv "$env:TEMP\soa-docs-venv"
& "$env:TEMP\soa-docs-venv\Scripts\python.exe" -m pip install -r api-gateway/tests/requirements-docs.txt
& "$env:TEMP\soa-docs-venv\Scripts\python.exe" -m unittest discover -s api-gateway/tests -p 'test_*.py'
```

Without the optional validator installed, the semantic-validation test is
explicitly skipped; CI installs it and runs all checks. Isolated real-Nginx
integration tests check documentation during bootstrap outages, after discovery
reloads, local asset MIME types, HEAD/redirect behavior, rejected documentation
writes, unknown assets, and existing JWT forwarding/internal-route blocks. They
use mock backends and never contact real services or the project database.

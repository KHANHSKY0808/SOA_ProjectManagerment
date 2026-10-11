# Task: Consul discovery on a shared Docker Compose network

Status: Cancelled at the user’s explicit request. Do not implement or cut over this plan.

## Objective
Remove the Windows/Docker DNS split that breaks topic-to-academic name lookup. Run Gateway, Consul and the four gateway-facing Django services on a shared Compose network, with discovery enabled and stable service DNS names.

## Findings
- Current Gateway and Consul run in Docker; auth, academic and topic run on Windows loopback.
- The Docker-managed Windows hosts entry for host.docker.internal points to an old LAN IP. Container DNS differs, so a passing Consul check does not imply reachability from the Windows topic process.
- Only api-gateway currently has a Dockerfile/Compose file.
- Auth/academic/topic already use database/DB_ProjectManagerment.db. Regist currently exposes health/admin only, has no domain models, and defaults to its own db.sqlite3. Log also has no domain models and is outside gateway/discovery; it is not required for this request path.

## Scope
- Add root Compose deployment for api-gateway, consul, auth-service, academic-service, regist-service and topic-service on one private bridge network.
- Preserve ports 8000/8001/8002/8003/8004/8500 and gateway prefixes. Expose local host ports on loopback; Django binds 0.0.0.0 inside containers.
- Services register their Compose DNS names with Consul using unique IDs. Gateway and service clients use http://consul:8500, with discovery enabled for topic/academic/auth identity/name lookup clients.
- Add reusable Django container build/entrypoint and explicit secret-safe build exclusions. Use existing dependency pins; no host package installations or automatic migrations.
- Mount the existing shared database directory at the same relative application path for auth/academic/topic. Preserve table ownership and managed=False mappings. No schema or production data mutations.
- Give the current registration skeleton its own persistent storage path through a minimal environment-selectable database setting; do not implement registration business logic or silently repoint its storage to another owner's tables.
- Frontend stays on Windows/Vite and continues calling Gateway :8000. Log service remains unchanged and outside the main request path.
- Add isolated deployment/configuration tests, CI checks and run/rollback documentation. Keep the existing gateway-only workflow available.
- Build and test before switching running services. After reviewable artifacts/checks are ready, present the exact cutover and rollback commands for final approval; then stop only verified old processes/containers and start the new stack.

## Constraints
- Before plan approval, write only fe/.agents/task.md and plan.md.
- Do not edit Windows hosts, firewall, existing per-service local .env files, dependencies, migrations or database schema.
- Secrets are read from existing local service env files / environment, excluded from image contexts and never printed or committed. Committed examples contain placeholders only.
- Preserve completed topic CRUD/UI work and other existing edits.
- Do not remove old containers or volumes, run compose down -v, or delete databases. Rollback must retain the previous deployment.

## Acceptance criteria
- Compose validates and all images build with existing requirements.
- Health endpoints and Consul registrations use container DNS, without LAN IP or host.docker.internal for internal stack traffic.
- Discovery remains enabled; topic-to-academic and academic-to-auth lookup transport resolves within the shared network.
- Isolated tests verify actual name enrichment, JWT handling and healthy service selection. Real deployment verification uses health/registry and authorized read-only contracts; no live topic/user writes or fabricated live user JWTs.
- Existing Django checks/tests, Gateway tests and relevant CI pass. If no authenticated live session is available, document the final browser/account verification gap precisely.
- Cutover happens only after a concrete reviewed deployment is approved; failed cutover restores old services without touching stored data.

## Risks and limitations
- Container builds need network/package availability and disk space. Do not change dependency versions implicitly if builds fail.
- SQLite shared-file writes remain a project deployment exception and can contend across containers; Docker networking does not solve write contention.
- Current fixed ports are occupied, so final cutover interrupts local requests briefly.
- Per-process environment can override .env; Compose must explicitly set container transport options and shared secret consistency without exposing values.
- Existing example files contain credential-like literals; replace literals with placeholders in touched examples, but do not rotate live credentials without a separately approved action.
- Registration and logging domain features are not implemented by this networking task.

## Cancellation
The user cancelled the Docker Compose/network plan. No infrastructure implementation or runtime cutover was performed. Existing containers, running services, configuration and database remain unchanged by this plan. Earlier topic CRUD changes remain in place.

# Plan: Shared Compose network with Consul discovery

Status: Cancelled at the user’s explicit request. Do not implement or cut over this plan.

## Ordered steps
1. After approval, inventory current settings, dependency compatibility, existing listener/process identity and Docker resources. Inspect database schema/ownership read-only; preserve unrelated edits and never print secrets.
2. Add a root Docker Compose project and reusable Django Dockerfile/entrypoint using the existing Python/dependency versions. Exclude .env files, database files, venv, .git, node_modules and backups from build context. Preserve root-relative service/database paths.
3. Configure the six containers (Consul, Gateway, auth, academic, registration, topic) on one Compose network. Register auth-service:8001, academic-service:8002, regist-service:8003 and topic-service:8004; health URLs use the corresponding DNS names. Container clients/Gateway use consul:8500 and explicit discovery=true overrides. Keep all public ports/prefixes unchanged.
4. Mount the existing database directory for auth/academic/topic with no startup migrations. Add an environment-controlled registration database path and persistent volume for its existing skeleton, preserving current defaults outside Compose. Containers must fail clearly if required storage/secrets are missing, rather than silently create a replacement shared database.
5. Add safe environment examples, deployment/config tests and an isolated smoke workflow. Verify discovery/name lookup with disposable fixtures and test-only identities/keys; never create live records or mint tokens for real user identities.
6. Update Python CI to validate/build the root stack and run isolated networking checks; retain existing service and Gateway test jobs. Update root, Gateway and affected service READMEs with startup, credentials, ports, storage, limitations and rollback instructions. Remove credential literals only from touched public example files; preserve real local credentials.
7. Run root compose validation/build, affected Django checks/tests, Gateway tests and the isolated smoke checks. Record evidence and failures honestly; do not cut over unverified artifacts.
8. Present final cutover commands, verified process/container targets, storage backup procedure and rollback steps for explicit final approval. Until then leave the existing running services/containers untouched.
9. After cutover approval, make a consistent SQLite backup through its backup API (no schema changes), stop only verified old listeners/containers without deleting them, and start the new stack. Check registry/health, Gateway forwarding and authorized read-only enrichment. Roll back on failure; update task/plan with results.

## Expected files
- fe/.agents/task.md, fe/.agents/plan.md
- Root compose.yaml, .dockerignore, .env.example (if needed), README.md
- docker/Dockerfile.django, docker/entrypoint.sh (or equivalent scoped build scripts)
- tests for deployment configuration and isolated Compose smoke checks, plus optional isolated test overlay
- services/regist-service/config/settings.py and config/tests.py (optional environment-controlled storage location)
- services/auth-service/.env.example, services/academic-services/.env.example, services/topic-service/.env.example, services/regist-service/.env.example as needed for documented container configuration/placeholders
- api-gateway/README.md and affected service READMEs
- .github/workflows/python-tests.yml
- Post-cutover approval only: local untracked backup artifact, new containers/images/network and registration storage volume. Existing per-service .env files and real database contents remain unchanged.

## Verification
- docker compose config --quiet (never print interpolated secrets), image builds and build-context secret/database exclusion checks.
- Affected python manage.py check/test commands with disposable test DBs and no live network dependencies.
- Existing Gateway discovery/unit/integration tests.
- Isolated stack: container DNS, health checks, Consul service addresses/healthy selection, Gateway routing, topic-to-academic and academic-to-auth actual name lookup, invalid/missing JWT rejection, container restart/discovery recovery. Use temporary fixture storage and test-only credentials.
- No host.docker.internal/LAN addresses in the new internal stack configuration; no generated migrations or source DB edits; git diff --check and scoped review.
- Final live health/registry/read-only checks only after cutover approval; report unavailable authenticated UI testing rather than forge a live JWT.

## Rollback
Before cutover, source edits/builds do not affect current runtime. After approved cutover, stop the new Compose services without removing volumes, restart the exact retained old Consul/Gateway containers and Windows Django commands, and verify original health/ports. Backups remain local and untracked. Restore database content only if a separately verified need arises; this task performs no production record writes or migrations. Revert only task-introduced files/lines, retaining existing topic CRUD and other work.

## Cancellation
The user cancelled the Docker Compose/network plan. No infrastructure implementation or runtime cutover was performed. Existing containers, running services, configuration and database remain unchanged by this plan. Earlier topic CRUD changes remain in place.

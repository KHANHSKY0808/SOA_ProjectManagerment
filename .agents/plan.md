# Plan: Cascading topic deletion through service contracts

Status: Completed after explicit approval (ok).

1. Inspect existing topic/regist service discovery, HTTP clients, permissions, routing and deletion tests. Preserve prior feature edits.
2. Add an authenticated, integer role1/2 authorized bulk DELETE contract for registrations belonging to one topic in regist-service. Delete active and cancelled rows within a local transaction, make repeated cleanup safe, and return a minimal explicit result DTO. No student/user deletion and no foreign table access.
   Expected files: RegistTopic management views/services/urls/serializers as needed, backend tests.
3. Extend topic-service DELETE orchestration: verify authorization/topic first, set its status to closed (0) locally before external cleanup, call regist-service using existing Consul/static-development conventions with forwarded JWT/request ID and bounded timeout, then delete the topic locally. Do not hold SQLite write transactions during network calls. Preserve foreign-key enforcement, safe storage/dependency errors and explicitly report a partial outcome when cleanup may have completed but topic deletion did not. Do not automatically retry writes. Topic remains closed on failure to prevent new registrations; caller must explicitly retry after inspecting outcome.
   Expected files: topic_manager services/views/client module and relevant tests; settings only if a new development service URL/timeout is required, following existing environment patterns.
4. Update frontend deletion confirmation and error/reconciliation handling to describe linked registration history deletion and partial outcomes. Preserve existing confirmation, duplicate-click lock and uncertain-result checks.
   Expected files: TopicDeleteModal.tsx, useTopics.ts, TopicPage.test.tsx, topic-api tests/types only as needed.
5. Add backend tests for linked/unlinked topic deletion, all registration statuses, topic isolation, integer role authorization, repeated cleanup, failed/time-out dependency, database rollback/conflict and partial completion. Add frontend confirmation/error tests.
6. Run affected services manage.py check and manage.py test; frontend tests, lint and production build (including TypeScript check); git diff --check. Do not invoke DELETE against live records.
7. Document the REST contract, permissions, timeout and partial-failure behavior in root/topic-service/regist-service/frontend READMEs. Update these task records with actual verification.

## Rollback
Revert only changes belonging to this task; retain previous roster/cancellation features and unrelated files. No schema or migration rollback needed. Reverting code cannot restore registration history deleted by later user actions; that requires a pre-existing database backup. No live deletion is part of implementation verification.

## Completed work and verification
- Added role1/2 bulk registration DELETE with explicit topic/count DTO, local transactional purge of all statuses and topic isolation. Individual cancellation remains soft cancellation.
- Topic deletion closes the topic, calls regist-service over discovered authenticated REST, then deletes its own topic; bounded timeout, no redirect/write retry, request-ID propagation and explicit partial-failure errors.
- Frontend confirmation warns of permanent registration-history deletion; failures require result checks and explicit renewed confirmation.
- Updated root and affected frontend/topic/regist READMEs, including new environment configuration, REST contract and non-atomic failure limitations.
- Topic-service: Django check and all 61 tests passed. Regist-service: Django check and all 39 tests passed. Frontend: lint, all 401 tests, TypeScript check and production build passed. git diff --check passed.
- Read-only runtime probes found one healthy regist-service in Consul and gateway registration health returned ok. No live DELETE or domain writes were issued; no authenticated browser walkthrough was performed.
- Existing modified database/DB_ProjectManagerment.db was present before implementation and preserved. No schema, migration, package, port, gateway or infrastructure modifications.

## Runtime correction within approved deletion rollout
- Old conflict response persisted because verified topic-service listener PID43540 (parent41440) used --noreload on127.0.0.1:8004. Duplicate workspace topic runserver chain5264/26276/29704/47112 was also present.
- Complete the approved rollout by stopping only verified workspace topic-service runserver processes and starting one hidden replacement using the same service venv, workspace, port and --noreload command. Preserve all other services, databases and configuration.
- Service-venv Django check passed before restart. Verify replacement listener plus direct/gateway health without live deletion. Logs: .agents/topic-service-runtime.stdout.log and .stderr.log. Runtime rollback uses the same previously verified startup command after stopping only the replacement; restart changes no source or domain data.

Runtime correction result: stopped only the six verified topic-service runserver processes; replacement parent39328/listener42464 now serves127.0.0.1:8004. Service-venv Django check passed; direct and gateway topic health both200. No live DELETE, migrations, service configuration changes or database mutations performed.

## Local development binding correction (approved deletion feature scope)
- Read-only health probe: discovered host.docker.internal:8003 timed out from Windows, while127.0.0.1:8003 returned200. The native topic-service therefore cannot use the Docker-facing registry address for its cleanup call.
- Configure the existing explicit local-development option in services/topic-service/.env: REGISTRATION_DISCOVERY_ENABLED=false and REGISTRATION_BASE_URL=http://127.0.0.1:8003. Preserve Consul registrations, Gateway, ports, credentials and other environment values. Restart only verified workspace topic-service runserver processes to reload configuration.
- Verify the effective client config and a health GET using its resolved base, plus direct/Gateway topic health. No live DELETE. Existing automated configuration tests cover explicit development binding. Roll back by removing these two new env keys and restarting only topic-service; this restores the prior discovery setting.

Local binding correction verified: effective REGISTRATION_CLIENT discovery=false/base=http://127.0.0.1:8003/timeout2; selected registration base health, direct topic health and Gateway topic health all returned200. Topic-service listener36500 (parent48344). Service-venv Django check and 8 targeted client/config tests passed. No live DELETE performed.

## HTTP topic UUID repair - 2026-10-11 (approved; completed)
1. After approval, inspect relevant frontend configuration/tests and compare affected Windows/Linux files; create rollback copies of affected Linux sources and current /var/www/soa-frontend outside Git in a private backup directory.
2. Add fe/src/features/topics/topic-id.ts implementing cryptographic UUID v4 generation, with native randomUUID fast path and getRandomValues fallback; add topic-id.test.ts covering fallback format/version/variant, missing/failing randomness and native branch.
3. Update fe/src/features/topics/useTopics.ts to call the helper and provide an accurate safe generation error; update TopicPage.test.tsx with an HTTP-like missing-randomUUID dialog regression and no-write failure coverage, retaining one-GUID-per-draft and existing reconciliation tests.
4. Update README.md and fe/README.md to describe UUID fallback and retain production HTTPS guidance. No changes to auth refresh, department duplicate handling or backend policies are included.
5. Run focused frontend tests, then full tests, lint and production build with VITE_API_BASE_URL=/. Resolve failures before deployment; do not modify dependency manifests or locks.
6. Sync only approved changed source/docs to Linux after verifying remote preconditions and backing up originals. Build on server using existing Node 24 Docker tooling. Stage/check output, deploy assets before replacing index.html at existing static root, and verify HTTP site/API routing and fallback in browser context without POSTing topics. Do not change Nginx/Gateway or other websites.
7. Record changed files, test results, deployment and limitations in task/plan.
Expected repository changes: fe/src/features/topics/topic-id.ts (new), fe/src/features/topics/topic-id.test.ts (new), fe/src/features/topics/useTopics.ts, fe/src/features/topics/TopicPage.test.tsx, README.md, fe/README.md, .agents/task.md, .agents/plan.md. Deployment additionally updates generated fe/dist and served frontend assets only; private rollback copies remain outside Git.
Rollback: restore affected Linux source/docs and the prior served frontend from private backups; revert only this task's local source changes while preserving unrelated edits. No backend restart, database restore, migration or token rotation is required.

### HTTP UUID repair completion
Approved by user (ok); completed and deployed on 2026-10-11.
- Added topic-id.ts and topic-id.test.ts; updated useTopics.ts, TopicPage.test.tsx, root README.md and fe/README.md. Uses native randomUUID or cryptographic getRandomValues with UUID v4 version/variant bits; retains the existing draft ID and reconciliation behavior.
- Local and Linux: all 410 frontend tests passed, lint passed, production build including TypeScript checks passed with VITE_API_BASE_URL=/.
- Deployed assets first and atomically replaced /var/www/soa-frontend/index.html. Served HTML/JS/CSS matched the build; all four gateway health routes returned HTTP 200.
- Chrome headless on the real HTTP origin confirmed insecure context, unavailable randomUUID, working create dialog, valid UUID v4 and a new ID for a new draft. API responses were mocked and zero mutation requests occurred. This does not verify a live topic POST.
- No backend/configuration/dependency/schema changes. Server database SHA256 remained 19e9092aa1aa31f4d04bcf19abc53b2824f08b9d996a8270d16bc924d6d8c53d.
- Private rollback source/served backups: /home/yang/.local/state/soa-config-backups/frontend-uuid-20261011T121556Z. Restore only affected source/docs and prior served frontend if rollback is needed.

Final audit note: the database matched the baseline immediately after deployment, but differed at the final read-only audit while the application remained live. This task performed no database writes or restore; the cause of the later change was not investigated.

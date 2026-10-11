# Task: Delete topics together with linked registrations

Status: Completed after explicit approval (ok).

## Objective and scope
Change the topic deletion flow so an authorized administrator or lecturer can permanently delete the topic and all registrations linked to that topic, including cancelled registrations. Update the confirmation dialog to explain the full deletion scope.

## Evidence
The current topic-service delete rejects database foreign-key conflicts. Read-only inspection of database/DB_ProjectManagerment.db found Registrations.TopicId references Topics.TopicId with NO ACTION. No other table currently references Topics or Registrations through a declared foreign key.

## Constraints
- Only task.md and plan.md may be written before approval.
- Preserve existing integer role1/2 management authorization, service ports and public route prefixes.
- Topic-service owns topics; regist-service must delete registrations through an authenticated REST contract. No cross-service table queries, ORM imports or database cascade changes.
- Delete only registrations for the selected topic, not students, lecturers, users or unrelated topics. Unlike individual cancellation, topic deletion permanently removes linked registration history.
- No schema changes, migrations, dependencies or infrastructure changes; preserve unrelated workspace edits and untracked databases.
- No actual deletion of user data during development/verification. Disposable test data and mocked clients only.

## Acceptance criteria
- Confirming topic deletion removes all linked registrations and then the topic; an unreferenced topic still deletes successfully.
- Unauthorized requests cannot delete topic or registration data. Invalid IDs cannot broaden deletion scope.
- Cleanup is idempotent and protected by management authorization on both services; bounded HTTP timeout and discovery follow existing conventions.
- Safe responses for unavailable services, storage failures and concurrent references; no blind write retries or success claims after partial failure.
- Confirmation explicitly states that linked registrations and their history will also be permanently deleted.
- Automated success, authorization, isolation, dependency-failure and frontend regression tests pass; affected Django checks and full tests, frontend lint/typecheck/build pass.

## Assumptions and risks
- Existing shared management permission allows both admin and lecturer to delete topics; retain this policy.
- Two independent services cannot share one atomic database transaction via REST. If registration cleanup succeeds but topic deletion fails, registrations may already be permanently removed; return a clear partial-result response and allow explicit retry after checking the topic.
- Close registration on the target topic before cleanup to reduce races. An already in-flight registration may still create a reference; the existing foreign key must prevent orphaning and a safe conflict must require explicit retry.
- No production data is changed by this coding task. Future confirmed deletions cannot be undone by reverting code; recovery requires an existing database backup.

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
Objective: allow opening a new topic draft at http://100.72.148.90:8080 without the HTTPS/localhost UUID error.
Evidence: fe/src/features/topics/useTopics.ts calls crypto.randomUUID() directly; this method is unavailable in insecure HTTP contexts. Existing draft/request reconciliation already depends on retaining one GUID per draft.
Scope: add a small UUID v4 helper that uses native crypto.randomUUID when available and crypto.getRandomValues otherwise, preserving UUID version/variant bits and one ID per draft. Update the draft hook, automated tests, and root/frontend documentation. Build and deploy the frontend to the existing Linux Nginx static directory, synchronizing only approved frontend source/docs to the server.
Constraints: never use Math.random or timestamps for IDs; no new dependency, API/backend/database/schema/JWT/port/Nginx changes; no production topic creation during verification; preserve existing unrelated local/server work. HTTP support for this UUID operation does not replace production HTTPS.
Acceptance: the create dialog opens with a valid UUID v4 when randomUUID is absent; repeated form edits/submission reconciliation retain the draft ID; native UUID behavior remains; missing/failing secure randomness produces safe feedback and no POST. Relevant and full frontend tests, lint and build pass. Deployed HTTP bundle is verified in a browser or equivalent browser-context smoke check without creating domain records.
Risks/assumptions: browser must support crypto.getRandomValues. Existing Windows workspace and Linux source may differ, so inspect/compare affected files before syncing and preserve unrelated differences. Static deployment briefly changes browser bundle versions; retain private rollback copies of affected sources and prior served assets. No live topic creation is authorized.

### HTTP UUID repair completion
Approved by user (ok); completed and deployed on 2026-10-11.
- Added topic-id.ts and topic-id.test.ts; updated useTopics.ts, TopicPage.test.tsx, root README.md and fe/README.md. Uses native randomUUID or cryptographic getRandomValues with UUID v4 version/variant bits; retains the existing draft ID and reconciliation behavior.
- Local and Linux: all 410 frontend tests passed, lint passed, production build including TypeScript checks passed with VITE_API_BASE_URL=/.
- Deployed assets first and atomically replaced /var/www/soa-frontend/index.html. Served HTML/JS/CSS matched the build; all four gateway health routes returned HTTP 200.
- Chrome headless on the real HTTP origin confirmed insecure context, unavailable randomUUID, working create dialog, valid UUID v4 and a new ID for a new draft. API responses were mocked and zero mutation requests occurred. This does not verify a live topic POST.
- No backend/configuration/dependency/schema changes. Server database SHA256 remained 19e9092aa1aa31f4d04bcf19abc53b2824f08b9d996a8270d16bc924d6d8c53d.
- Private rollback source/served backups: /home/yang/.local/state/soa-config-backups/frontend-uuid-20261011T121556Z. Restore only affected source/docs and prior served frontend if rollback is needed.

Final audit note: the database matched the baseline immediately after deployment, but differed at the final read-only audit while the application remained live. This task performed no database writes or restore; the cause of the later change was not investigated.

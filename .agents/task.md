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

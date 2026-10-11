# Implementation plan: Student topic registration APIs

Status: Approved by user. Commit provider contracts, registration APIs, and final
documentation/verification as separate important milestones.

## Proposed public contract (gateway paths)
1. POST /registrations/api/v1/registrations/
   Body: {"topic_id":"DT001","semester":"2026-1"}; semester optional.
   201 new record; 200 existing identical current registration; 409 already has
   a different current topic. Student identity comes only from JWT.
2. GET /registrations/api/v1/available-topics/
   200 list: only topic status 1 in the authenticated student's faculty.
3. GET /registrations/api/v1/registrations/
   200 own registration records; optional status=active|cancelled filter.
4. DELETE /registrations/api/v1/registrations/{registration_id}/
   204 soft cancellation (including already cancelled); 404 unknown/non-owner.

All require valid access JWT with integer role 3. Define explicit request/response
serializers and stable error codes: 400 invalid input/ineligible topic, 401 invalid
JWT, 403 wrong role/missing student eligibility, 404 missing resource, 409 conflicting
registration, 503 dependency/storage unavailable. Preserve /health/.

## Ordered steps and files
1. Recheck affected files and read-only schema/status usage after approval. Map
   Registrations with managed=False, explicit column metadata and cross-service
   scalar IDs in services/regist-service/RegistTopic/models.py. Do not migrate.
2. Add small authenticated academic contracts for the caller's student/faculty
   context and batch major-to-faculty lookup. Use JWT identity for self lookup and
   support text IDs. Expected files: academic-services/config/urls.py, new
   registration_context.py and test_registration_context.py. No Users ORM access.
3. Add an authenticated topic registration lookup contract returning minimal topic
   metadata including major_id and status, with list/status and detail lookup.
   Expected files: topic-service/topic_manager/{urls,views,serializers,tests}.py
   or dedicated registration lookup module/test module. Preserve existing DTOs
   and management behavior. Provider services only read their own tables.
4. Implement bounded academic/topic HTTP clients in regist-service, discover
   healthy academic-service/topic-service instances through Consul, allow explicit
   static development URLs only when discovery is disabled. Set timeouts (default
   3 seconds), bounded response/batch sizes and circuit breaker (3 failures,
   10-second cooldown); no automatic write retries or external calls in tests.
   Forward JWT and sanitized correlation ID; deny redirects carrying credentials.
   Document call limits and use batch lookups to avoid per-topic faculty calls.
5. Implement local JWT authentication, student permission, DTOs, transactional
   registration/cancellation logic, correlation-ID audit logs without sensitive
   payloads, safe storage/dependency errors and API routes. Expected files:
   regist-service/RegistTopic/{authentication,permissions,serializers,clients,
   services,views,urls,tests}.py and config/{settings,urls}.py.
   Configure shared database path and JWT key via environment; use existing
   dependencies. Cancellation affects only Registrations and preserves history.
6. Add tests against disposable SQLite tables for unmanaged mappings; mock REST
   calls. Cover same-faculty/different-major acceptance, closed/missing/cross-faculty
   topics, role/identity denial, owner filtering/cancellation, cancellation then
   re-registration, duplicate/idempotent requests, concurrent creates, legacy
   statuses, dependency/discovery failures, timeouts/circuit recovery and locking.
   Add provider contract tests and ensure no tests modify the project database.
7. Update README.md, services/{regist-service,academic-services,topic-service}/README.md
   and regist-service/.env.example for routes, examples, authorization, error/status
   meanings, discovery, timeout/rate expectations and operational limitations.
   Existing requirements and CI matrix already cover all three services; change
   neither unless new evidence requires a separately reviewed scope adjustment.

## Verification
- Run targeted tests during development using available existing Python environments.
- Run manage.py check and manage.py test in regist-service, academic-services and
  topic-service, with safe test configuration and auto-registration disabled.
- Check final diff for secrets, accidental database/migration/infrastructure changes,
  unauthorized cross-service queries and interference with user's frontend files.
- Do not claim live Gateway/Consul integration verification from mocked unit tests.

## Database compatibility and rollback
- No schema changes, migrations, index creation or production-data cleanup.
- Existing physical database ownership: auth owns Users; academic owns Students,
  Majors and Faculties; topic owns Topics; registration owns Registrations.
- Keep HTTP validation outside SQLite write locks and atomically serialize
  registration checks/writes using the database, across worker processes.
- No database backup is needed for code-only implementation/tests on disposable
  databases. Before any future live writes operators should back up the shared
  SQLite database consistently; this plan does not authorize a live data exercise.
- Roll back only this task's code/docs/config-example changes; preserve unrelated
  work. Deployed registration/cancellation data must not be deleted by code rollback.
- Material changes to this scope require updates to both plans and renewed approval.

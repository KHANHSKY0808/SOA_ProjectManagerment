# Task: Topic status column and registered students in topic detail

Status: Completed after user approval (ok).

## Objective
Show topic status on the management table and the students registered for a topic in its detail popup.

## Scope
- Add Vietnamese topic status column using existing labels: 0 pending, 1 approved, 2 open; safe fallback for null/unknown.
- Add management-only registered-student list in topic detail for JWT integer role1/admin and role2/lecturer, following existing shared topic management policy.
- Add read-only regist-service endpoint scoped to topic ID, with bounded cursor pagination and explicit DTOs.
- Add minimal academic student display-name batch lookup restricted to roles1/2, reusing existing service-authenticated auth name client. No contact details or academic scores exposed.

## Constraints
- Before approval write only root .agents/task.md and plan.md; no source edits, network calls, dependency/config/runtime/database changes.
- Registrations remain owned by regist-service, student records by academic-service, names/identity by auth-service. No cross-service ORM imports or foreign-owned table reads.
- Preserve ports, routes, topic status semantics and student registration APIs. No schema/model changes, migrations, database writes, new packages, infrastructure or secrets changes.
- Preserve all unrelated workspace changes. New source changes require automated tests.

## Acceptance criteria
- Management table displays a labelled status column; empty table colspan and responsive layout remain correct.
- Admin/lecturer topic detail loads registered students independently from core topic detail, with loading, empty, failure/retry and bounded load-more behavior.
- Student role3/unknown roles cannot access new management list/name APIs or see the roster UI; unauthenticated requests401, unauthorized roles403.
- Roster returns only records for requested topic; cancelled status0 excluded. Existing current-registration semantics (nonzero or null) preserved with clear labels for legacy status.
- Roster columns: student ID, name, semester, registration date. Missing names display a fallback; failure must not be presented as an empty roster. Optional name lookup failure preserves registration IDs/data and signals partial enrichment.
- Request abort/unmount/close prevents stale list updates; no automatic retry or domain writes.
- Affected Django check/test and frontend tests/typecheck/lint/build pass. Root and affected service/frontend READMEs document new contracts and permissions.

## Assumptions
- “Sinh viên đăng ký” means current registrations, excluding cancelled records; full historical registration display is outside scope.
- Both admin and lecturer use this management detail, consistent with existing shared topic management authorization. Students do not receive other students' roster.
- Unknown/missing topic may return an empty roster at registration service because service owns only registration records; popup core topic read still reports missing topics.

## Risks
- Full academic profiles contain unnecessary personal fields; use a minimal name-only lookup instead.
- Name enrichment depends on academic/auth availability and existing internal credentials. Preserve rows/IDs and show incomplete-name notice on failure.
- Large rosters require bounded100-row pages and batched lookups, avoiding full student downloads or one request per student.
- Current manually started services and --noreload processes may require targeted reload for live verification after code changes. No runtime change before approval.


## Delivery and verification
- Added topic collection status typing/parser validation and status column with existing Vietnamese labels; updated fixtures including App route regression fixture.
- Added management roster API + minimal academic student-name lookup, permissions for integer roles1/2,100-row pagination and partial-name fallback. Existing auth name client reused unchanged; no auth-service change required.
- Added independent cancellable roster hook/API, loading/empty/error/retry/load-more UI in topic detail; no request for student role3.
- Updated root, frontend, regist-service and academic-service READMEs with contracts and behavior.
- Academic: manage.py check passed; all150 tests passed.
- Regist: manage.py check passed; all34 tests passed; after partial-name flag improvement the3 roster tests passed again.
- Frontend: all378 tests passed across16 files, lint passed, production build/typecheck passed. git diff --check passed.
- Reloaded only verified academic --noreload chain; replacement launcher48360/listener45760. Removed old regist --noreload duplicate19904/23820; kept active autoreload listener41172. No other service restarted.
- Direct academic/regist health200; both new Gateway routes401 without JWT (correct protected routes). Academic/auth internal credentials are configured and equal (never displayed), with explicit local auth name transport.
- No database/schema/migrations/dependencies/config/infrastructure changes. No live domain writes or fabricated JWTs. Automated role/data behavior verified; authenticated browser/manual layout walkthrough unavailable in this session.

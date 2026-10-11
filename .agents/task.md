# Task: Diagnose student registration dependency_unavailable

Status: Approved by user (ok); read-only diagnosis performed, awaiting failing authenticated request evidence.

## Objective
Resolve the reported Vietnamese lookup-unavailable message in student registration after topic status changes.

## Evidence and scope
- Frontend maps dependency_unavailable to the exact reported message.
- Registration context, topic lookup and major/faculty lookup can all produce this code on transport, upstream auth/status or DTO failures.
- Ports 8001-8004, 8000 and 8500 have listeners. Registration development config points to academic 127.0.0.1:8002 and topic 127.0.0.1:8004 with discovery disabled explicitly.
- Current topic and registration processes use autoreload; stale code is not established as the cause.
- Diagnose bounded read-only local HTTP/REST calls, safe configuration and relevant logs. Repair only the identified client/contract/config defect.

## Constraints
- Before approval only root .agents/task.md and plan.md may be changed; no HTTP calls yet.
- Preserve status meanings 0 pending, 1 approved, 2 open; preserve registration record status semantics.
- No production domain writes, fabricated JWTs, credentials disclosure, database/schema/migrations, installs, container or infrastructure changes.
- Existing database file and fe/.agents modifications are unrelated current workspace changes and must be preserved.
- A targeted service restart is permitted only after identity/port/startup command verification and only if evidence requires it.

## Acceptance criteria
- Identify failing dependency and concrete cause from actual response/transport evidence; do not mask 503 with an empty list or bypass validation/authentication.
- Repair the confirmed cause with automated regression tests for source changes.
- Affected Django check/test passes; frontend tests/typecheck/lint/build if frontend changes.
- Verify read-only local routing and dependency behavior; authenticated verification requires a legitimate available session, otherwise report that gap.

## Assumptions and risks
- User confirms failure occurs when opening the student available-topics list.
- Missing legitimate session may limit reproducing protected lookups. Do not print bearer tokens or personal data in logs/results.
- Current environment and database can change independently while diagnosing. Avoid broad resets or replacing user work.


## Read-only diagnosis findings
- Direct health for academic/topic/regist and Gateway registration health returns 200.
- Academic registration-context, topic registration-topics and regist available-topics respond 401 without credentials as expected; this proves reachability, not authenticated success.
- JWT_SIGNING_KEY values in the four local .env files are present and equal (values never displayed). Active process environment overrides are not verified.
- Configured database paths resolve to the shared database with expected tables. Topic status counts show one open (2) and one legacy null record; no data was changed.
- Existing processes use runserver autoreload. No restart or configuration change performed without evidence of a cause.
- Browser inventory returned no connected apps or browsers, so there is no available legitimate authenticated session for reproducing protected read requests.
- Requested failing Network request name/status/response from the user, excluding credentials. Exact failed dependency and cause remain unconfirmed; no speculative repair performed.


## Follow-up evidence and diagnostic instrumentation
- User supplied available-topics response code dependency_unavailable and generic reference-services detail. Exact dependency remains unknown.
- Added safe warning logs in RegistTopic/clients.py identifying service, operation, failure stage, exception type, upstream HTTP status and sanitized request ID. No paths, payloads, credentials or exception text logged.
- Added automated tests for HTTP/timeout/DTO/circuit diagnostic logs and absence of credentials, personal IDs and log injection.
- manage.py check passed; all 30 regist-service tests passed. README documents diagnostics.
- Need user to refresh available-topics and provide the new Reference lookup failed console line because no connected authenticated browser session or access to existing service console is available. No cause or completed repair claimed.

Targeted restart complete: launcher 19904, listener 23820 on 127.0.0.1:8003, Gateway registration health 200. Diagnostic logs at TEMP/soa-regist-diagnostic-22bebb07c7e8406dace5a9c225f2806b.{out,err}.log. Waiting for legitimate user refresh; no authenticated request or confirmed cause yet.

Confirmed multiple duplicate root-venv regist-service processes; listener identity switched including old --noreload process30484. Removed only verified duplicate regist processes; sole remaining listener23820 with diagnostic logs. Gateway health200. Authenticated frontend refresh still required to verify lookup success and distinguish old code from dependency transport failure.


## Confirmed runtime cause and repair
- Captured authenticated available-topics failure: topic-service operation=topic_page stage=request error=URLError. Registration history returns 200; academic context passed before topic failure.
- Direct topic health connection failed with WinError10061; no process/listener existed on8004. Missing topic-service runtime is the confirmed lookup failure cause.
- Started existing topic-service venv manage.py runserver127.0.0.1:8004 --noreload in hidden window. Launcher41440/listener43540; logs TEMP/soa-topic-diagnostic-8797dc48e1644f4f9889b4016cc86bd1.{out,err}.log.
- Topic direct health200, Gateway topic health200 after discovery refresh; Consul topic-service-8004 checks passing. Gateway registration health200.
- Duplicate registration service processes removed; one diagnostic registration listener retained. Source diagnostic checks/tests passed previously (30 tests). No database/config/schema changes made for runtime repair.
- Awaiting another authenticated available-topics refresh to confirm end-to-end success; do not claim that protected list has returned200 yet.


## Corrected wrong service on academic port
- After user restarts,8002 health returned service=auth-service and registration-context returned404. The logged academic context upstream404 matches this runtime misconfiguration.
- Stopped only verified auth-service venv runserver8002 chain3348/19308/39636/34240; auth-service8001 retained.
- Started academic-services existing venv from correct directory on127.0.0.1:8002 --noreload. Launcher27536/listener20768; TEMP/soa-academic-repair-7f772cab28674184b11827f54d37be5a.{out,err}.log.
- Verified8001 auth health200,8002 academic health200,8004 topic health200 and Gateway academic health200. Academic registration-context now401 without token instead of404, proving correct protected route exists.
- User requested to refresh after10-second circuit cooldown. Authenticated list success remains to be verified. No schema/data/config changes.


## Resolution verified
- User's legitimate browser refresh at10:54:18 produced available-topics200, academic registration-context200, major-departments200 and topic registration-topics200. Gateway log independently confirms available-topics200.
- Subsequent user action at10:54:25 produced registration POST201 and history GET200. Agent did not issue any domain write; only observed existing service logs.
- Runtime lookup failure resolved. Correct service identity on academic8002 and topic availability on8004 restored; safe diagnostic logging/tests/docs retained. All30 regist-service automated tests and Django check passed for source diagnostic change.
- Existing multiple manual service processes remain a runtime maintenance concern; avoid launching duplicates. No schema, migration, dependency or production data edits by agent.

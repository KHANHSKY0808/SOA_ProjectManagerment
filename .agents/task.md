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

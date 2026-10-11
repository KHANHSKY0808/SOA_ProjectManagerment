# Plan: Repair student registration lookup failure

Status: Approved by user (ok); diagnosis in progress.

1. After approval, compare bounded local health and unauthenticated read endpoint responses through Gateway/direct services, inspect safe active configuration and relevant existing logs. Use legitimate connected session only if available; never fabricate credentials or create/cancel registrations to diagnose.
2. Trace failing student action through academic registration-context, topic registration-topics and academic major-departments contracts. Check transport, JWT configuration equality without displaying secrets, status 2 eligibility and DTO validation. Read Consul state only when relevant to actual active routing.
3. Apply the smallest confirmed fix. Expected possible files: services/regist-service/RegistTopic/{clients,services,test_clients,test_api}.py, services/topic-service/topic_manager/{registration_lookup,test_registration_lookup}.py; academic registration context/major-department handlers and their tests if confirmed defective; affected service config/settings.py and config tests if needed. Local ignored .env transport values may be corrected without exposing or committing secrets.
4. If runtime reload is necessary, verify process ID, executable, working directory and command, record prior startup/config for rollback, then restart only the affected Django service in a hidden window. Keep ports, service names and Gateway prefixes unchanged. No container restart or infrastructure changes.
5. Add regression tests for source fixes. Run smallest relevant tests then affected manage.py check/test. Frontend changes limited to confirmed registration DTO/error-handling defects with tests and existing npm checks; do not hide upstream failures.
6. Update root/affected service/frontend READMEs only when behavior/config/run guidance changes. Record actual cause, changed files, verification and remaining session limits in task/plan and delivery.

## Rollback
Revert only new follow-up edits, preserving previously approved status implementation and unrelated workspace modifications. Restore only altered local config values and the affected service's verified prior startup command. No database or domain record changes are included. If diagnosis requires schema, infrastructure, secrets rotation or broader changes, request a revised approval first.


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

## Targeted registration logging restart
- Verified current 8003 listener PID 25244; parent chain 23160 -> 4784 -> 46164 -> VS Code terminal PowerShell 14936. All four Python processes run repository root venv manage.py runserver 8003.
- Stop only verified Python chain PIDs 46164,4784,23160,25244 after rechecking identities. Leave PowerShell terminal and other service processes untouched.
- Replacement: root venv Python, working directory services/regist-service, manage.py runserver 127.0.0.1:8003 --noreload, hidden window; stdout/stderr files under OS TEMP, no source config change.
- Rollback: stop only replacement launcher/listener after identity verification; run root venv manage.py runserver 8003 from services/regist-service in original terminal. Original config unchanged. Historical dormant processes without this listener are not touched.

Confirmed duplicate regist runserver processes on port 8003. Listener switched between 25244,24148 and old 30484 during diagnosis. Stop only verified root-venv Python manage.py runserver 8003 duplicates, preserving managed diagnostic launcher19904/listener23820; no other services/terminal touched. Duplicate process IDs recorded below.

ProcessId ParentProcessId
--------- ---------------
    25972            6800
    30484           25972
    19904           46476
    23820           19904
    32136           14936
    50024           32136
    45740           50024
    24148           45740




Live diagnosis: authenticated refresh logs topic-service/topic_page stage=request URLError. Direct 127.0.0.1:8004 health confirms WinError10061 connection refused; no listener or topic runserver process exists. Start missing topic-service using its existing venv, working directory services/topic-service, runserver127.0.0.1:8004 --noreload, hidden window with TEMP logs. No configuration or data changes. Rollback stops only newly started verified topic launcher/listener, restoring absence of topic runtime.


## Confirmed runtime cause and repair
- Captured authenticated available-topics failure: topic-service operation=topic_page stage=request error=URLError. Registration history returns 200; academic context passed before topic failure.
- Direct topic health connection failed with WinError10061; no process/listener existed on8004. Missing topic-service runtime is the confirmed lookup failure cause.
- Started existing topic-service venv manage.py runserver127.0.0.1:8004 --noreload in hidden window. Launcher41440/listener43540; logs TEMP/soa-topic-diagnostic-8797dc48e1644f4f9889b4016cc86bd1.{out,err}.log.
- Topic direct health200, Gateway topic health200 after discovery refresh; Consul topic-service-8004 checks passing. Gateway registration health200.
- Duplicate registration service processes removed; one diagnostic registration listener retained. Source diagnostic checks/tests passed previously (30 tests). No database/config/schema changes made for runtime repair.
- Awaiting another authenticated available-topics refresh to confirm end-to-end success; do not claim that protected list has returned200 yet.

Confirmed new root cause after user restarts:8002 health identifies auth-service; registration-context returns404. Verified wrong-port auth process chain3348,19308,39636,34240 uses auth-service venv runserver8002. Stop only this chain, preserve correct auth8001. Start academic-services existing venv runserver127.0.0.1:8002 --noreload from academic-services directory. Rollback stops replacement academic process only; wrong auth8002 original command recorded but should not be restored for normal operation. No config or port change.

ProcessId ParentProcessId
--------- ---------------
     3348           31736
    19308            3348
    39636           19308
    34240           39636





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

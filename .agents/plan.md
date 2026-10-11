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

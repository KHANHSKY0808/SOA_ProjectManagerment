# Task: Fix student registration service-unavailable error

Status: Completed. Local runtime configuration repaired and routing verified.

## Objective
Restore the failing API flow reported as topic detail with detail "Service
unavailable." at http://localhost:5173/student/registrations.

## Read-only findings
- StudentRegistrationPage requests /registrations/api/v1/registrations/ and
  /registrations/api/v1/available-topics/. It does not call topic detail directly.
- The exact string "Service unavailable." exists in Gateway Nginx config/rendering
  for no healthy upstream and for translated upstream 502/504 failures.
- topic-service storage/dependency errors and regist-service dependency errors have
  different messages. The reported string points toward Gateway; the exact failed
  Network request still needs verification.
- Local listeners exist on 8000, 8500 and 8001-8004. Django ports 8001-8004 are
  listening on 127.0.0.1, which alone does not establish container reachability.
- No live HTTP/Consul/Docker inspection or state change has been performed yet.

## Scope and constraints
- Diagnose local Gateway, Consul and registration/topic/academic transport with
  read-only bounded requests, safe logs/config inspection and process identity.
- Fix only the confirmed route/discovery/reachability or reference-client cause.
  Preserve ports, names, prefixes, service boundaries, JWT policy and database.
- If needed, adjust only relevant non-secret local transport settings and restart
  only the verified affected Django process/instance. Do not print .env secrets,
  process command-line secrets, tokens or user profile data.
- Do not restart/recreate containers, change Windows hosts/firewall, implement
  the cancelled Compose migration, install dependencies, change schemas/migrations,
  touch unrelated fe/.agents edits, or create live registration/topic records.
- Any Gateway infrastructure change, broader deployment/network migration or other
  material scope expansion requires a revised plan and renewed approval.
- Add regression tests for code changes; commit meaningful repair milestones per
  the user's existing preference. Local .env values are never committed.

## Acceptance criteria
- Identify the exact failing request and distinguish no upstream, unreachable
  service, service exception and downstream validation failure with evidence.
- Gateway reaches a healthy regist-service; topic/academic references are reachable
  through configured discovery/development transport without bypassing auth.
- Existing student registration list/open-topic flow returns correct results with
  an available legitimate student session, or report the precise authenticated
  verification gap. Do not forge real-user tokens.
- No live mutation or schema change. Relevant tests/checks pass for changed code.
- Document the cause, repair, safe verification and rollback; preserve unrelated work.

## Assumptions and risks
- Source-only search cannot distinguish missing registry instances from live
  connection/timeouts. A generic frontend error is not evidence of a bad DTO.
- Loopback-only listeners may be unreachable from Docker; Consul address/health
  and current container routing must be checked rather than assumed.
- Restarting an affected Django development service can briefly interrupt requests;
  verify its executable, directory and port ownership before any targeted restart.
- Live JWT/session may be unavailable. A protected endpoint returning 401 proves
  basic routing, not student eligibility or an end-to-end successful detail read.

## Outcome

Cause confirmed: absent regist .env left Consul auto-registration disabled and
Gateway with no registration upstream. Created local ignored configuration with
shared JWT and explicit Windows development client transport, restarted only
regist-service, and verified its healthy discovery/routing. Direct/Proxy health
and protected-route responses now behave correctly; all 29 tests and Django check
passed. Authenticated browser verification remains unavailable; no production
record or database schema was changed. Only documentation/planning files are
committed; the real .env stays ignored.

# Plan: Diagnose and repair student registration 503

Status: Completed after approval; local configuration repair verified.

1. Read-only local diagnosis after approval: identify failed registration API using
   available browser/session or bounded unauthenticated requests; compare Gateway
   versus direct service responses. Read relevant Consul health/service entries,
   safe Gateway connectivity/discovery logs and effective non-secret transport
   settings. Inspect only process identity/listeners and relevant paths, no secrets.
2. Trace available-topics and registration validation through regist-service's
   academic/topic clients. Verify healthy service addresses from each caller's
   network context. Use current public health and authorized read-only contracts;
   never issue registration/cancellation/topic writes for diagnosis.
3. Choose the smallest evidence-backed repair within approved scope. Expected
   possible files: relevant service config/settings.py or config/consul.py and tests;
   RegistTopic/clients.py and test_clients.py if a client defect is confirmed;
   local untracked transport-only .env values if configuration is the cause.
   No speculative frontend fallback, static hidden production dependency or JWT
   bypass. If only runtime configuration is wrong, do not invent source changes.
4. For a required Django restart, record the verified existing process/instance,
   original bind/transport values and rollback command first. Change/restart only
   the affected service, preserve other listeners/containers and existing data.
   Re-registration may use the existing affected service's register_consul command
   when needed. No container/infrastructure mutation is included in this plan.
5. Add regression tests for confirmed source changes. Run targeted tests followed
   by affected manage.py check/test; frontend lint/test/typecheck/build only if
   frontend code actually changes. No dependency installation or migrations.
6. Verify local health, Consul healthy instance and Gateway reachability again.
   Verify read-only student data with a legitimate session if available; otherwise
   report the remaining session-specific gap. No fabricated production JWTs.
7. Update only relevant README run/troubleshooting guidance if behavior/settings
   change. Expected docs: root README, regist/topic/academic README as affected,
   plus these root planning files. Commit important source/doc milestones without
   unrelated frontend planning files, secrets, logs or databases.

## Rollback
Restore only changed non-secret transport values and the affected service's prior
verified startup command/registration. Revert task-specific code/docs commits if
needed. Do not delete database files, containers, volumes or legacy registrations.
If the necessary fix falls outside scope, document findings and request approval
for an updated concrete plan before applying it.

## Confirmed diagnosis and targeted restart record
- Gateway /registrations/health/ and both student GET APIs return 503; direct
  regist health returns 200 and protected GET returns 401 as expected without JWT.
- Consul has no regist-service instances; active Gateway configuration explicitly
  returns 503 for /registrations/. Docker-to-host regist health is reachable (200).
- services/regist-service/.env is absent. All three other service files have the
  same configured JWT_SIGNING_KEY (only equality checked, never printed).
- Consul advertises host.docker.internal for academic/topic, but that hostname's
  health URLs are unreachable from the Windows caller. For this Windows-local
  development process, configure explicit ACADEMIC/TOPIC_DISCOVERY_ENABLED=false
  and loopback BASE_URL values; Gateway still uses Consul discovery normally.
- Add the ignored local regist .env with common JWT key, registry auto-registration
  enabled, existing regist-service-8003 identity and unchanged host/health settings.
- Verified original listener PID 50408, Django autoreloader parent PID 35624,
  root venv Python launcher; both are manage.py runserver 8003 processes. Only
  those verified processes may be stopped. Replacement uses root venv Python,
  working directory services/regist-service, manage.py runserver 8003 --noreload,
  hidden window, temporary stdout/stderr files outside the repository.
- Rollback: stop only replacement PID after identity verification, restore the
  prior absence of local .env (securely remove only this created file), and run
  original root venv Python with manage.py runserver 8003 in that directory.
  Deregister only this instance if reverting the registration. No other process,
  container, host/firewall setting or database is changed.

## Repair verification

- Created only ignored services/regist-service/.env, using the existing common
  JWT key (never printed/committed), registry auto-registration and explicit
  Windows-local academic/topic client URLs.
- Restarted only verified old registration launcher/listener. Replacement launcher
  PID 25972 and Python listener PID 30484; other services/containers untouched.
- Consul passing regist-service-8003 now exists with passing HTTP/agent checks.
- Gateway registration health: 200. Gateway registration history/open-topic and
  Vite-proxied open-topic requests without credentials: 401, no longer Gateway 503.
- Academic registration context and topic registration lookup via configured
  loopback URLs: 401 without credentials, confirming reachable protected routes.
- Root-venv manage.py check passed; manage.py test passed all 29 regist tests.
- No source code, frontend, dependency, infrastructure or database change was
  needed. Updated README troubleshooting; no new implementation regression tests
  are required for an ignored local runtime configuration repair.
- No browser connection was available; actual authenticated student read and
  downstream faculty filtering remain unverified. No forged JWT or live domain
  write was used to fill this gap. User can refresh the existing student page.

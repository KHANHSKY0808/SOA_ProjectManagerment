# Plan: Management cancellation from topic roster

Status: Completed after explicit approval (ok).

1. Add management detail route /registrations/api/v1/topics/{topic_id}/registrations/{registration_id}/, using existing role1/2 permission.
   - DELETE verifies owned registration/topic match inside transaction with existing acquire_write_lock, sets status0 and server audit metadata, returns204; already cancelled is idempotent.
   - GET returns minimal registration_id/topic_id/status DTO including cancelled status, for exact result reconciliation; matching topic required. No names/profile lookup needed.
   Expected files: services/regist-service/RegistTopic/{management_roster,urls,services,test_management_roster}.py as appropriate.
2. Add typed frontend cancel/status API methods with encoded IDs, Bearer/abort signal, strict response validation and no automatic retries.
   Expected files: fe/src/features/topics/roster-api.ts and roster-api.test.ts.
3. Extend useTopicRoster with selection/confirmation, busy lock, success/error messages and uncertain-result state. Remove only the cancelled registration row on confirmed success, preserve other loaded rows and cursor. Reconcile exact GET after ambiguous failure; keep action locked while uncertain until reconciliation or deliberate popup close after request completion. Never infer success from absence on first page.
   Expected file: fe/src/features/topics/useTopicRoster.ts.
4. Add Thao tác column and Hủy đăng ký row button, inline confirmation with student identity, confirm/back controls and checking-result action. Bind modal busy state to cancellation so close/Escape and competing actions cannot interrupt an active submission; keep topic detail visible. Handle missing names by student ID.
   Expected files: fe/src/features/topics/components/TopicDetailModal.tsx, topics.css only if layout needs adjustment, TopicPage.test.tsx.
5. Regression tests: roles1/2 success, role3/string/bool/unknown denial, JWT audit actor, wrong-topic isolation, idempotent repeat, legacy-null cancellation, storage rollback, exact GET status; UI confirmation/back, duplicate write/close lock, successful row removal, HTTP errors, ambiguous-result GET reconciliation and no automatic retries.
6. Run targeted tests then regist-service manage.py check and manage.py test; frontend test/typecheck/lint/build. Tests use disposable databases/mocked HTTP only. No live cancellation of user records.
7. Update README.md, services/regist-service/README.md and fe/README.md with new management contract/permissions and confirmation/reconciliation behavior. Record verification in task/plan.
8. If API reload is needed, verify service identity/current listener/process/start command first. Reload only affected regist-service on unchanged8003; use hidden window for a replacement and record rollback/log paths. Do not restart unrelated services or containers.

## Rollback
Revert only this task's code/tests/docs changes, preserving previous roster/status work and unrelated untracked database files. No production data/schema modifications included. Restore prior verified service startup if reload occurs. Soft cancellations performed later by users remain historical status0 records and are not automatically reversed by code rollback.

## Verification and outcome
- Implemented management GET/DELETE registration detail and confirmed soft cancellation with JWT audit metadata, scope validation, and idempotency.
- Added frontend confirmation, busy protection, row removal, and exact-state reconciliation after ambiguous failures.
- Regist-service Django check and all 37 backend tests passed. Frontend lint, all 401 tests, TypeScript check and production build passed.
- Gateway read-only probes verified the service health and authentication on the new route. Existing regist-service auto reload was sufficient; no service configuration changes or live registration cancellations were performed.
- Updated root, regist-service and frontend READMEs. No schema, dependency or infrastructure changes. Authenticated browser walkthrough was not performed.

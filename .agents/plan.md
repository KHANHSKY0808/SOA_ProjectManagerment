# Plan: Student registration UI at /student

Status: Completed after user approval ("ok").

## Ordered implementation and expected files
1. Add typed registration API adapter and response validation in
   fe/src/features/registrations/registration-api.ts with registration-api.test.ts.
   Reuse apiClient and published Gateway routes/DTOs. Validate identity/status/page
   shape, cursor progress and mutation results; pass AbortSignal to every call.
2. Build StudentRegistrationPage.tsx, useStudentRegistrations.ts and scoped
   registrations.css (split components where useful). Reuse the current layout
   and accessible Modal. Show current-registration summary, eligible-topic table,
   optional semester input and confirmed registration/cancellation, plus history.
   Handle initial loading, partial failures, notices, reload and cursor load-more.
   Deduplicate appended rows; keep search explicitly scoped to loaded topics.
3. Implement Vietnamese error-code mapping, synchronous submit guard and abort/
   request-generation protection. Lock mutation actions until own history is
   successfully refreshed after ambiguous writes. No automatic mutation retry;
   offer an explicit result-check action and preserve failures visibly.
4. Wire fe/src/app/App.tsx so role-3 index /student and its existing registrations
   child route render the new feature. Adjust student-only menu/title handling in
   dashboard-menu.ts/MainLayout.tsx only if necessary for coherent labels.
   Keep existing roles, guards, profile, academic and topic routes compatible.
5. Add StudentRegistrationPage.test.tsx and update App.test.tsx plus affected
   layout tests if needed. Cover successful register/cancel, active restrictions,
   unknown legacy status, field/code errors, 401/403/409/503, independent loading
   failures, filtered empty pagination, duplicate submit, ambiguous write result
   reconciliation, stale response/unmount and student-only routing.
6. Update fe/README.md and root README to replace student registration placeholder
   claims, document route behavior, pagination/search, optional semester, history,
   API errors, verification and remaining live-integration limitations.
7. Run targeted tests then npm run test, npm run lint, npm run typecheck and npm
   run build using existing dependencies. Review scoped diff, document results,
   and commit important milestones (API adapter; UI/routes/tests; final docs).

## Verification and rollback
- Use mocked HTTP/UI tests, with no live registration/cancellation writes.
- Existing node_modules/tooling only; do not install packages or edit locks.
- Check UTF-8 Vietnamese text, responsive CSS and accessible dialog behavior.
- Preserve unrelated fe/.agents changes and backend implementation commits.
- Revert only this task's commits/files for rollback. No database/runtime rollback
  is needed because this task does not change backend state or running services.
- Material scope changes require updating both planning files and renewed approval.

## Delivery and verification

- c0c8082: typed Gateway API adapter, response validation and 30 contract tests.
- f8a3a0f: student page, request lifecycle, safe errors, registration/cancellation
  confirmation, history reconciliation, responsive CSS and route/UI tests.
- npm run test: 341 tests / 15 files passed; npm run lint, npm run typecheck and
  npm run build passed. Build artifacts are ignored, not committed.
- No backend/schema/infrastructure/dependency/lockfile/.env changes. No live
  registration writes or external service calls. Existing fe/.agents modifications
  remain untouched and uncommitted.
- Verification uses jsdom and API mocks; no live student account/Gateway integration
  or visual-device testing was performed. Documentation states these limitations.

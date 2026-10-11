# Task: Cancel a student's registration from topic detail

Status: Completed after explicit approval (ok).

## Objective and scope
Add a cancel-registration action to each student row in the topic management detail popup, backed by a management-authorized regist-service operation.

## Constraints
- Before approval write only .agents/task.md and .agents/plan.md.
- Reuse existing integer-role1/admin and role2/lecturer shared topic management policy. Student role3 cannot invoke the management operation.
- Cancellation sets registration status0; retain history, student/topic IDs and other registration data. Do not hard-delete records.
- Regist-service owns registration changes; frontend sends topic_id and registration_id in the path, never a trusted actor/status value.
- Preserve ports/prefixes, student self-cancellation contract, topic status semantics and SOA boundaries.
- No schema/model changes, migrations, new dependencies, secrets/config/infrastructure changes or live domain writes during verification.
- Preserve unrelated untracked services/regist-service/db.sqlite3 and other workspace edits.

## Acceptance criteria
- Each current roster row has a Hủy đăng ký button for admin/lecturer only.
- Inline confirmation names the targeted student (ID/name), with confirm and back actions before sending cancellation.
- Backend verifies integer role1/2 and registration belongs to the path topic; forged mismatched topic/registration IDs404 and no changes.
- Successful DELETE returns204, status becomes0, UpdatedAt updated and UpdatedBy set from authenticated JWT. Repeated cancellation returns204 without rewriting audit fields.
- Cancelled row disappears from current roster and a success notice appears; remaining rows and pagination remain usable.
- Prevent duplicate submissions and closing/switching actions while saving. On timeout/network/5xx do not auto-retry; reconcile the exact registration status through an authorized GET before offering another write.
- Unauthenticated401, unauthorized403, missing404, storage503 handled safely; no other student's registration is changed.
- Automated backend/frontend tests and required checks pass; affected READMEs document API and UI behavior.

## Assumptions and risks
- Both admin and lecturer may cancel within the existing shared topic-management policy; no new advisor-only ownership restriction is implied.
- Hủy đăng ký means soft cancellation (status0), matching existing student cancellation, not deletion of historical records.
- A paginated list alone cannot establish cancellation after an uncertain response; exact-registration status lookup is needed for reconciliation.
- A concurrent registration/create must remain synchronized by existing SQLite write-lock pattern. Cancellation should not depend on academic/auth name availability.

## Verification and outcome
- Implemented management GET/DELETE registration detail and confirmed soft cancellation with JWT audit metadata, scope validation, and idempotency.
- Added frontend confirmation, busy protection, row removal, and exact-state reconciliation after ambiguous failures.
- Regist-service Django check and all 37 backend tests passed. Frontend lint, all 401 tests, TypeScript check and production build passed.
- Gateway read-only probes verified the service health and authentication on the new route. Existing regist-service auto reload was sufficient; no service configuration changes or live registration cancellations were performed.
- Updated root, regist-service and frontend READMEs. No schema, dependency or infrastructure changes. Authenticated browser walkthrough was not performed.

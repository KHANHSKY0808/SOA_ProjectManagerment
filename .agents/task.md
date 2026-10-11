# Task: Student registration frontend

Status: Approved by user ("ok"); implement with milestone commits.

## Objective and scope
Implement the four approved registration capabilities in fe for student role 3:
open topics in the student's faculty, register, view own registration history,
and cancel. Show the feature directly at /student and keep the existing
/student/registrations menu URL working with the same screen.

## Constraints
- Before approval, write only root .agents/task.md and .agents/plan.md.
- Preserve existing uncommitted fe/.agents/task.md and fe/.agents/plan.md; these
  contain a cancelled infrastructure plan and are not part of this frontend task.
- Use existing React/TypeScript/Axios, role guards, layout, modal and CSS patterns.
- Call Gateway /registrations/api/v1/* with existing bearer-token handling.
  No direct service URLs, new dependencies, backend/schema/environment changes.
- Backend remains authoritative for faculty/status and registration uniqueness.
  Never send student_id or client-controlled registration/audit status.
- Preserve admin/lecturer screens and role authorization.
- Continue the user's requested milestone commits, scoped to this task's files.

## Acceptance criteria
- /student presents current registration, eligible topic list and own history;
  /student/registrations provides the same capabilities via existing navigation.
- Topics support explicit search within loaded pages, load-more cursor pagination,
  empty pages with a non-null cursor, refresh, loading/error/empty states.
- Register accepts topic_id and optional semester, with confirmation; current
  registrations (including legacy nonzero/null statuses) disable another register.
- Cancellation requires confirmation, preserves visible history and enables
  registration again after confirmed refreshed state.
- Mutation buttons prevent double submit; failed/unknown writes are never retried
  automatically. Reconcile through own registration list before allowing another
  write after timeout/network/5xx/invalid mutation response.
- Handle backend stable error codes in Vietnamese, including faculty mismatch,
  closed topic, conflict, permission and dependency/storage errors. 401 follows
  existing logout flow. Stale requests cannot overwrite newer/user-changed state.
- Accessible dialogs/buttons/status messages and usable mobile layout.
- Meaningful API/UI/route tests, npm test, lint, typecheck and build pass.
- Update fe/README.md and root README; report mocked vs live verification precisely.

## Assumptions and risks
- /student is the requested entry screen, replacing its generic overview for role 3.
- Reuse the existing /student/registrations menu path; no new admin registration UI.
- API pagination filters a source page, so empty results can still have next_after.
  Do not interpret one empty page as the end, and do not auto-fetch all pages.
- Registration history DTO includes topic_id, optional semester, status and times,
  not guaranteed display names. Show the topic code always; use a name only when
  actually available from loaded eligible topics, without inventing metadata.
- Status 0 is cancelled; all other statuses conservatively count as current.
- No live student account or browser/backend integration is assumed available.
- Earlier backend task/verification history remains recorded in existing commits.

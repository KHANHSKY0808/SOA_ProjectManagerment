# Task: Student topic registration APIs

Status: Approved by user; implement and commit each important milestone.

## Objective
Implement four student-facing capabilities in regist-service: register a topic,
list topics open for registration in the student's faculty, list the student's
registrations, and cancel the student's registration.

## Scope
- regist-service owns and maps only the existing Registrations table.
- Validate JWTs locally; require integer role 3 and derive StudentId from JWT user_id.
- Obtain student/faculty and topic data through documented, authenticated REST
  contracts in academic-services and topic-service; add minimal supporting APIs.
- Preserve the repository's documented existing topic-service:8004 ownership
  exception, current ports, gateway prefixes, auth contract and existing DTOs.
- Add automated tests and update root/affected service documentation and environment examples.
- No frontend work, package installation, schema changes, migrations, live service
  startup, infrastructure changes or edits to real .env secrets.

## Rules and proposed semantics
- A student may have at most one current registration, across all semesters.
- Register only when topic status is exactly integer 1 and both faculties exist
  and match. Faculty is derived through Students.MajorId -> Majors.FacultyId and
  Topics.MajorId -> Majors.FacultyId; matching major alone is not required.
- Proposed registration status: 1 = current; 0 = cancelled. Legacy other/null
  statuses conservatively count as current until their meaning is established.
- Cancellation preserves the record, timestamps and server-derived actor; after
  cancellation a student can register again. Listing includes current and cancelled
  records, with a documented optional status filter.
- Only the token owner's registrations may be listed/cancelled; reject submitted
  identity/audit/status overrides. Request creation accepts topic_id and optional
  semester (the existing column is nullable; no semester requirement was requested).
- Repeated creation of an already-current topic returns the existing registration;
  a different current topic returns 409. Repeated owner cancellation is idempotent.

## Acceptance criteria
- Four documented versioned APIs work through /registrations/* with student JWTs.
- Closed topics, different/missing faculties, missing student/topic, duplicate
  current registration and non-owner/non-student requests are rejected safely.
- Concurrent writes cannot create two current registrations through this service.
- Dependency timeouts/invalid responses/unhealthy discovery fail safely with 503;
  no auth/academic/topic tables are queried by regist-service.
- Relevant automated success, validation, authorization, dependency and concurrency
  tests pass along with manage.py check/test for every affected service.
- Existing health endpoints, APIs and CI commands remain compatible.

## Inspection evidence, assumptions and risks
- Registrations currently has RegistrationId primary key and nullable StudentId,
  TopicId, Semester, Status, Notes, Reason, CreatedAt, UpdatedAt, UpdatedBy.
- Its only unique index is RegistrationId: no student uniqueness constraint exists.
  Use an SQLite write transaction acquired before checking/inserting (not merely
  a process mutex or select_for_update) and keep network calls outside the lock.
  SQLite contention returns a safe retryable response; no blind write retries.
- Registration status meanings are not defined in the current empty service.
  The proposed semantics above require approval as part of this plan.
- Existing public topic DTOs omit major IDs for role 3; student CRUD detail routes
  use integer path IDs despite text database IDs. Supporting APIs must handle text
  IDs without breaking existing routes or exposing identity/profile data.
- Existing frontend planning files fe/.agents/task.md and plan.md are modified;
  leave those unrelated changes untouched.
- Cross-service validation is a point-in-time check, not a distributed transaction;
  faculty/topic status may change after validation. No topic capacity limit requested.
- No production data/schema writes occur during verification. Legacy duplicate
  registrations must be reported/handled conservatively, never silently repaired.

## Completion

Implemented the four approved capabilities with student JWT ownership, faculty/status
validation over REST, single-current-registration transactions, preserved cancellation
history, versioned reference contracts and automated tests. All 225 affected-service
tests and Django checks passed. Live Gateway/Consul testing and frontend work remain
outside this task; no database schema/data or infrastructure changes were made.

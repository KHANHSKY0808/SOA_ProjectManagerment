# Plan: Topic status and management roster

Status: Completed after user approval (ok).

1. Inspect affected tests/permissions and current contracts; preserve existing student self-service registration endpoints unchanged.
2. Add GET /registrations/api/v1/topics/{topic_id}/registrations/?after={registration_id} with integer roles1/2 only. Query owned Registrations by topic and current status, order registration_id ascending, limit101 to return100 plus next_after. DTO fields: registration_id, student_id, student_name(nullable), semester, status, created_at; page includes names_unavailable flag. Reject invalid cursor/extra filters where appropriate. No need to query foreign Topic/Student tables.
   Expected files: services/regist-service/RegistTopic/{urls,views,permissions,serializers,services,clients,test_api,test_clients}.py; optionally a dedicated management_roster.py and test_management_roster.py for clear separation.
3. Add POST /academic/api/v1/student-display-names/ with body {student_ids:[...]}, max100 and64KiB body, roles1/2 and bounded120/min lookup throttle. Query only owned Students IDs; reuse existing academic IdentityNamesClient to call auth internal name contract with service credentials. Return student_names mapping and names_unavailable flag. Extend identity-name client with compatible availability reporting if necessary; preserve existing lecturer fallback behavior. No auth-service contract change expected.
   Expected files: services/academic-services/config/urls.py, StudentManager/display_names.py and test_display_names.py, LectureManager/identity_client.py and its tests if necessary.
4. Add bounded academic name-client method in regist-service using existing ACADEMIC_CLIENT timeout/discovery and Bearer forwarding. No retries. Optional name failures produce null names and explicit partial-enrichment flag, not a failed/empty registration list. Preserve response security and correlation IDs. Existing auth transport keeps bounded timeout/circuit fallback.
5. Add required status field parsing to topic collection type, status labels in TopicTable and updated colspan/styles. Update topic API fixtures/tests so list payloads include status as returned by backend.
   Expected files: fe/src/features/topics/topic-api.ts, components/TopicTable.tsx, topics.css if needed, topic-api.test.ts and TopicPage.test.tsx.
6. Add typed management roster API and independent state/loading/retry/pagination to topic detail flow, only for management roles. Abort requests on close/unmount; preserve topic detail when roster fails. Show minimal student table and incomplete-name notice; handle401 logout and403 safely.
   Expected files: fe/src/features/topics/useTopics.ts, components/TopicDetailModal.tsx, topic-api.ts (or dedicated roster-api.ts), related API/UI tests.
7. Add regression tests covering topic statuses, role denial, topic isolation, excluded cancellations, legacy/null state, empty/list pagination, unavailable name lookup, malformed DTOs, loading/error/retry, no roster call for students and request cancellation. Run targeted tests then full manage.py check/test for academic-services and regist-service; frontend test/typecheck/lint/build. No live domain writes.
8. Update README.md, services/regist-service/README.md, services/academic-services/README.md, fe/README.md and planning outcomes. CI changes only if new commands/dependencies are actually required (none expected).
9. If live verification requires runtime reload, verify actual service identity, listener PID, process command and directory first; restart only affected Django services on unchanged ports in hidden windows, record logs and rollback commands. Use legitimate user session only; no fabricated JWTs or production registration writes.

## Rollback
Revert only this task's source/tests/docs edits, retaining earlier topic-status and lookup fixes plus unrelated workspace edits. New APIs are additive, no persisted data/schema change. Restore prior verified runtime commands if a targeted reload occurs. If broader schema/infrastructure/security policy changes become necessary, update task/plan and seek renewed approval first.

Runtime reload record: academic listener20768/launcher27536 uses academic-services venv manage.py runserver127.0.0.1:8002 --noreload and needs reload for new student name route. Replace only this chain with identical command/directory in hidden window, TEMP logs. Old regist launcher19904/listener23820 is a stale duplicate --noreload instance; stop only it and retain current autoreload regist chain25784/42760/26356/41172. Rollback uses recorded original academic command after reverting source; do not restore stale duplicate regist instance. Other services untouched.


## Delivery and verification
- Added topic collection status typing/parser validation and status column with existing Vietnamese labels; updated fixtures including App route regression fixture.
- Added management roster API + minimal academic student-name lookup, permissions for integer roles1/2,100-row pagination and partial-name fallback. Existing auth name client reused unchanged; no auth-service change required.
- Added independent cancellable roster hook/API, loading/empty/error/retry/load-more UI in topic detail; no request for student role3.
- Updated root, frontend, regist-service and academic-service READMEs with contracts and behavior.
- Academic: manage.py check passed; all150 tests passed.
- Regist: manage.py check passed; all34 tests passed; after partial-name flag improvement the3 roster tests passed again.
- Frontend: all378 tests passed across16 files, lint passed, production build/typecheck passed. git diff --check passed.
- Reloaded only verified academic --noreload chain; replacement launcher48360/listener45760. Removed old regist --noreload duplicate19904/23820; kept active autoreload listener41172. No other service restarted.
- Direct academic/regist health200; both new Gateway routes401 without JWT (correct protected routes). Academic/auth internal credentials are configured and equal (never displayed), with explicit local auth name transport.
- No database/schema/migrations/dependencies/config/infrastructure changes. No live domain writes or fabricated JWTs. Automated role/data behavior verified; authenticated browser/manual layout walkthrough unavailable in this session.

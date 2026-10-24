import uuid
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from .clients import academic_client, topic_client
from .models import Registration


class RegistrationConflict(APIException):
    status_code = 409
    default_detail = "Student already has a current registration."
    default_code = "registration_conflict"


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = "Registration storage is temporarily unavailable."
    default_code = "storage_unavailable"


class GPARequirementNotMet(APIException):
    status_code = 400
    default_detail = "Student GPA is below the topic requirement."
    default_code = "gpa_requirement_not_met"


class TopicQuotaFull(APIException):
    status_code = 409
    default_detail = "Topic student quota has been reached."
    default_code = "topic_quota_full"


def active_registrations():
    return Registration.objects.filter(Q(status__isnull=True) | ~Q(status=0))


def topic_student_counts(topic_ids):
    return dict(active_registrations().filter(topic_id__in=topic_ids).values("topic_id")
                .annotate(total=Count("student_id", distinct=True)).values_list("topic_id", "total"))


class RegistrationCancelled(APIException):
    status_code = 409
    default_detail = "Cancelled registrations cannot be graded."
    default_code = "registration_cancelled"


class TopicRegistrationClosed(APIException):
    status_code = 409
    default_detail = "Student cancellation is closed for this topic."
    default_code = "topic_registration_closed"


class TopicNotClosed(APIException):
    status_code = 409
    default_detail = "The topic must be closed before grading."
    default_code = "topic_not_closed"


def current_registrations(identity):
    return Registration.objects.filter(student_id=identity).filter(Q(status__isnull=True) | ~Q(status=0))


def acquire_write_lock():
    # SQLite reserves the writer lock before the duplicate read, across processes.
    with connection.cursor() as cursor:
        cursor.execute('UPDATE "Registrations" SET "RegistrationId" = "RegistrationId" WHERE 0')


def register(identity, data, authorization, request_id):
    context = academic_client.context(identity, authorization, request_id)
    topic = topic_client.topic(data["topic_id"], authorization, request_id)
    departments = academic_client.departments([topic["major_id"]], authorization, request_id)
    if topic["status"] != 2:
        raise ValidationError({"topic_id": "Topic is not open for registration."}, code="topic_closed")
    if not departments[topic["major_id"]] or departments[topic["major_id"]] != context["department_id"]:
        raise ValidationError({"topic_id": "Topic must belong to the student's faculty."}, code="faculty_mismatch")
    with transaction.atomic():
        acquire_write_lock()
        existing = list(current_registrations(identity)[:2])
        if existing:
            if len(existing) == 1 and existing[0].topic_id == data["topic_id"] and existing[0].semester == data.get("semester"):
                return existing[0], False
            raise RegistrationConflict()
        if context["gpa"] < topic["req_GPA"]:
            raise GPARequirementNotMet()
        if topic_student_counts([data["topic_id"]]).get(data["topic_id"], 0) >= topic["studentQuota"]:
            raise TopicQuotaFull()
        now = timezone.now()
        return Registration.objects.create(registration_id=str(uuid.uuid4()), student_id=identity,
                                           topic_id=data["topic_id"], semester=data.get("semester"), status=1,
                                           created_at=now, updated_at=now, updated_by=identity), True


def cancel(identity, registration_id, authorization, request_id):
    obj = Registration.objects.filter(pk=registration_id, student_id=identity).first()
    if obj is None:
        raise NotFound("Registration not found.")
    if obj.status == 0:
        return
    topic = topic_client.topic(obj.topic_id, authorization, request_id)
    if topic["status"] == 3:
        raise TopicRegistrationClosed()
    with transaction.atomic():
        acquire_write_lock()
        obj = Registration.objects.filter(pk=registration_id, student_id=identity).first()
        if obj is None:
            raise NotFound("Registration not found.")
        if obj.status != 0:
            Registration.objects.filter(pk=obj.pk, student_id=identity).update(
                status=0, updated_at=timezone.now(), updated_by=identity)


def available_topics(identity, after, authorization, request_id):
    context = academic_client.context(identity, authorization, request_id)
    page = topic_client.page(after, authorization, request_id)
    rows = page["results"]
    departments = academic_client.departments([row["major_id"] for row in rows], authorization, request_id) if rows else {}
    counts = topic_student_counts([row["topic_id"] for row in rows])
    results = []
    for row in rows:
        if departments[row["major_id"]] != context["department_id"]:
            continue
        count = counts.get(row["topic_id"], 0)
        reason = ("gpa_requirement_not_met" if context["gpa"] < row["req_GPA"] else
                  "topic_quota_full" if count >= row["studentQuota"] else None)
        results.append({**row, "registered_count": count, "eligible": reason is None,
                        "ineligibility_reason": reason})
    return {"results": results, "next_after": page["next_after"]}


def get_topic_registration(topic_id, registration_id):
    obj = Registration.objects.filter(pk=registration_id, topic_id=topic_id).first()
    if obj is None:
        raise NotFound("Registration not found for this topic.")
    return obj


def require_topic_advisor(actor, topic_id, authorization, request_id):
    topic = topic_client.management_topic(topic_id, authorization, request_id)
    if topic["advisor_id"] != actor:
        raise PermissionDenied("Only the assigned advisor may access this topic's registrations.")
    return topic


def grade_topic_registration(actor, role, topic_id, registration_id, point, authorization, request_id):
    topic = (topic_client.management_topic(topic_id, authorization, request_id) if role == 1
             else require_topic_advisor(actor, topic_id, authorization, request_id))
    if topic["status"] != 3:
        raise TopicNotClosed()
    with transaction.atomic():
        acquire_write_lock()
        obj = get_topic_registration(topic_id, registration_id)
        if obj.status == 0:
            raise RegistrationCancelled()
        if obj.point == point:
            return obj
        now = timezone.now()
        Registration.objects.filter(pk=obj.pk, topic_id=topic_id).update(
            point=point, updated_at=now, updated_by=actor)
        obj.point, obj.updated_at, obj.updated_by = point, now, actor
        return obj


def cancel_topic_registration(actor, topic_id, registration_id):
    with transaction.atomic():
        acquire_write_lock()
        obj = get_topic_registration(topic_id, registration_id)
        if obj.status != 0:
            Registration.objects.filter(pk=obj.pk, topic_id=topic_id).update(
                status=0, updated_at=timezone.now(), updated_by=actor)


def purge_topic_registrations(topic_id):
    """Permanent topic cleanup, including cancelled history; local ownership only."""
    with transaction.atomic():
        acquire_write_lock()
        count, _ = Registration.objects.filter(topic_id=topic_id).delete()
        return count

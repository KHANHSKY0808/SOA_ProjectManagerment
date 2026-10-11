import uuid
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError
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
        now = timezone.now()
        return Registration.objects.create(registration_id=str(uuid.uuid4()), student_id=identity,
                                           topic_id=data["topic_id"], semester=data.get("semester"), status=1,
                                           created_at=now, updated_at=now, updated_by=identity), True


def cancel(identity, registration_id):
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
    return {"results": [row for row in rows if departments[row["major_id"]] == context["department_id"]],
            "next_after": page["next_after"]}

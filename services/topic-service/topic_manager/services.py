from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from .clients import academic_client
from .models import Topic


class Conflict(APIException):
    status_code = 409
    default_detail = "Topic conflicts with existing data or references."


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = "Topic storage is temporarily unavailable."


def get_topic(pk):
    try:
        return Topic.objects.get(pk=pk)
    except Topic.DoesNotExist:
        raise NotFound("Topic does not exist.") from None


def validate_references(data, authorization):
    references = []
    if "major_id" in data:
        references.append(("major_id", "majors", "major_id", data["major_id"]))
    if data.get("advisor_id"):
        references.append(("advisor_id", "lecturers", "lecturer_id", data["advisor_id"]))
    if references:
        academic_client.validate(references, authorization)


def save_topic(data, actor, authorization, pk=None, partial=False, *, role):
    if type(role) is not int or role not in (1, 2):
        raise PermissionDenied("Only administrators and lecturers may modify topics.")
    if role == 2 and "status" in data:
        raise PermissionDenied({"status": "Only administrators may change topic status."})
    obj = get_topic(pk) if pk is not None else None
    if obj is not None and data.get("topic_id", pk) != pk:
        raise ValidationError({"topic_id": "Topic ID cannot be changed."})
    validate_references(data, authorization)
    now = timezone.now()
    values = dict(data)
    if obj is None:
        values.setdefault("status", 1 if role == 1 else 0)
    if obj is not None:
        values.pop("topic_id", None)
        if not partial:
            for field in ("description", "file_url", "advisor_id"):
                values.setdefault(field, None)
    values.update(updated_at=now, updated_by=actor)
    try:
        with transaction.atomic():
            if obj is None:
                if Topic.objects.filter(pk=data["topic_id"]).exists():
                    raise Conflict({"topic_id": "Topic already exists."})
                return Topic.objects.create(created_at=now, **values)
            # UPDATE only: a concurrent deletion must never recreate a row.
            if not Topic.objects.filter(pk=pk).update(**values):
                raise NotFound("Topic does not exist.")
            return get_topic(pk)
    except IntegrityError:
        raise Conflict() from None
    except OperationalError:
        raise StorageUnavailable() from None


def delete_topic(pk):
    obj = get_topic(pk)
    try:
        with transaction.atomic():
            obj.delete()
    except IntegrityError:
        raise Conflict("Topic is referenced and cannot be deleted.") from None
    except OperationalError:
        raise StorageUnavailable() from None

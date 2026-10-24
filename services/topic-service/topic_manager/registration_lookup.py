"""Small, bounded topic reference DTOs for student registration clients."""
from django.db import OperationalError
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Topic


class StudentPermission(BasePermission):
    def has_permission(self, request, view):
        role = request.auth.get("role") if request.auth else None
        return bool(request.user and request.user.is_authenticated and type(role) is int and role == 3)


class TopicReferenceDTO(serializers.Serializer):
    topic_id = serializers.CharField()
    name = serializers.CharField()
    req_GPA = serializers.FloatField()
    studentQuota = serializers.IntegerField()
    major_id = serializers.CharField()
    status = serializers.IntegerField(allow_null=True)


class LookupQueryDTO(serializers.Serializer):
    after = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TopicStorageUnavailable(APIException):
    status_code = 503
    default_detail = "Topic storage is temporarily unavailable."


class RegistrationTopicView(APIView):
    permission_classes = [StudentPermission]

    def handle_exception(self, exc):
        return super().handle_exception(TopicStorageUnavailable() if isinstance(exc, OperationalError) else exc)

    def get(self, request, pk=None):
        if pk is not None:
            obj = Topic.objects.filter(pk=pk).first()
            if obj is None:
                raise NotFound("Topic not found.")
            return Response(TopicReferenceDTO(obj).data)
        query = LookupQueryDTO(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = list(Topic.objects.filter(status=2, topic_id__gt=query.validated_data["after"])
                    .order_by("topic_id")[:101])
        return Response({"results": TopicReferenceDTO(rows[:100], many=True).data,
                         "next_after": rows[99].pk if len(rows) > 100 else None})

"""Minimal student name lookup for authorized topic management readers."""
from django.db import OperationalError
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from LectureManager.display_names import BoundedJSONParser, ReaderLookupThrottle
from LectureManager.identity_client import identity_client
from .models import Student


class TopicManagerPermission(BasePermission):
    def has_permission(self, request, view):
        role = request.auth.get("role") if request.auth else None
        return bool(request.user and request.user.is_authenticated and type(role) is int and role in (1, 2))


class StudentNamesInput(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.CharField(max_length=255), max_length=100)

    def validate(self, attrs):
        if set(self.initial_data) != {"student_ids"}:
            raise serializers.ValidationError("Only student_ids is accepted.")
        attrs["student_ids"] = list(dict.fromkeys(attrs["student_ids"]))
        return attrs


class StudentNamesOutput(serializers.Serializer):
    student_names = serializers.DictField(child=serializers.CharField(allow_null=True))
    names_unavailable = serializers.BooleanField()


class StudentDisplayNamesView(APIView):
    permission_classes = [TopicManagerPermission]
    parser_classes = [BoundedJSONParser]
    throttle_classes = [ReaderLookupThrottle]

    def post(self, request):
        dto = StudentNamesInput(data=request.data)
        dto.is_valid(raise_exception=True)
        ids = dto.validated_data["student_ids"]
        names = dict.fromkeys(ids)
        try:
            existing = list(Student.objects.filter(pk__in=ids).values_list("student_id", flat=True))
        except OperationalError:
            error = APIException("Student names are temporarily unavailable.")
            error.status_code = 503
            raise error from None
        if existing:
            names.update(identity_client.names(existing))
        return Response(StudentNamesOutput({"student_names": names,
                                             "names_unavailable": any(value is None for value in names.values())}).data)

"""Academic-owned registration reference contracts; no identity database access."""
from django.db import OperationalError
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from StudentManager.models import Student
from MajorManager.models import Major
from DeparmentManager.models import Department


class StudentPermission(BasePermission):
    def has_permission(self, request, view):
        identity = request.auth.get("user_id") if request.auth else None
        role = request.auth.get("role") if request.auth else None
        return (bool(request.user and request.user.is_authenticated)
                and type(role) is int and role == 3
                and isinstance(identity, str) and bool(identity.strip()) and len(identity) <= 255)


class AcademicUnavailable(APIException):
    status_code = 503
    default_detail = "Academic storage is temporarily unavailable."


class ContextDTO(serializers.Serializer):
    student_id = serializers.CharField()
    department_id = serializers.CharField()
    gpa = serializers.FloatField()


class MajorBatchDTO(serializers.Serializer):
    major_ids = serializers.ListField(child=serializers.CharField(max_length=255), max_length=100)


class MajorDepartmentsDTO(serializers.Serializer):
    departments = serializers.DictField(child=serializers.CharField(allow_null=True))


class ReferenceView(APIView):
    permission_classes = [StudentPermission]

    def handle_exception(self, exc):
        return super().handle_exception(AcademicUnavailable() if isinstance(exc, OperationalError) else exc)


class RegistrationContextView(ReferenceView):
    def get(self, request):
        student = Student.objects.filter(pk=request.auth["user_id"]).first()
        department = (Major.objects.filter(pk=student.major_id).values_list("department_id", flat=True).first()
                      if student else None)
        if not department or not Department.objects.filter(pk=department).exists():
            raise PermissionDenied("Student has no valid faculty.")
        return Response(ContextDTO({"student_id": student.pk, "department_id": department, "gpa": student.gpa}).data)


class MajorDepartmentsView(ReferenceView):
    def post(self, request):
        dto = MajorBatchDTO(data=request.data)
        dto.is_valid(raise_exception=True)
        ids = dto.validated_data["major_ids"]
        result = dict.fromkeys(ids)
        result.update(Major.objects.filter(pk__in=ids).values_list("major_id", "department_id"))
        existing = set(Department.objects.filter(pk__in=[v for v in result.values() if v])
                       .values_list("department_id", flat=True))
        result = {key: value if value in existing else None for key, value in result.items()}
        return Response(MajorDepartmentsDTO({"departments": result}).data)

"""Topic roster management; registration persistence stays inside its owner."""
from django.db.models import Q
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from .clients import academic_client, DependencyUnavailable
from .models import Registration
from . import services
from .serializers import PointRequestDTO, PointResponseDTO
from .views import RegistrationAPIView


class TopicManagerPermission(BasePermission):
    def has_permission(self, request, view):
        role = request.auth.get("role") if request.auth else None
        return bool(request.user and request.user.is_authenticated and type(role) is int
                    and (role == 1 or (role == 2 and request.method in ("GET", "HEAD", "OPTIONS"))))


class TopicGraderPermission(BasePermission):
    def has_permission(self, request, view):
        role = request.auth.get("role") if request.auth else None
        return bool(request.user and request.user.is_authenticated and type(role) is int and role in (1, 2))


class RosterQuery(serializers.Serializer):
    after = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if set(self.initial_data) - {"after"}:
            raise serializers.ValidationError("Only after is accepted.")
        return attrs


class RosterStudent(serializers.Serializer):
    registration_id = serializers.CharField()
    student_id = serializers.CharField(allow_null=True)
    student_name = serializers.CharField(allow_null=True)
    semester = serializers.CharField(allow_null=True)
    status = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    point = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)


class RosterPage(serializers.Serializer):
    results = RosterStudent(many=True)
    next_after = serializers.CharField(allow_null=True)
    names_unavailable = serializers.BooleanField()


class RegistrationPurgeDTO(serializers.Serializer):
    topic_id = serializers.CharField()
    deleted_count = serializers.IntegerField(min_value=0)


class AdvisorReadMixin:
    def check_advisor(self, request, topic_id):
        if request.auth["role"] == 2:
            services.require_topic_advisor(
                request.auth["user_id"], topic_id,
                request.headers.get("Authorization", ""), self.request_id)


class TopicRegistrationsView(AdvisorReadMixin, RegistrationAPIView):
    permission_classes = [TopicManagerPermission]
    http_method_names = ["get", "delete", "head", "options"]

    def delete(self, request, topic_id):
        count = services.purge_topic_registrations(topic_id)
        return Response(RegistrationPurgeDTO({"topic_id": topic_id, "deleted_count": count}).data)

    def get(self, request, topic_id):
        self.check_advisor(request, topic_id)
        query = RosterQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = list(Registration.objects.filter(topic_id=topic_id,
                    registration_id__gt=query.validated_data["after"])
                    .filter(Q(status__isnull=True) | ~Q(status=0)).order_by("registration_id")[:101])
        page = rows[:100]
        ids = list(dict.fromkeys(row.student_id for row in page if row.student_id))
        names = dict.fromkeys(ids)
        incomplete = any(not row.student_id for row in page)
        if ids:
            try:
                lookup = academic_client.student_names(ids, request.headers.get("Authorization", ""), self.request_id)
                names.update(lookup["student_names"])
                incomplete = incomplete or lookup["names_unavailable"] or any(value is None for value in names.values())
            except DependencyUnavailable:
                incomplete = True
        results = [{"registration_id": row.pk, "student_id": row.student_id,
                    "student_name": names.get(row.student_id), "semester": row.semester,
                    "status": row.status, "created_at": row.created_at, "point": row.point} for row in page]
        return Response(RosterPage({"results": results,
                        "next_after": page[-1].pk if len(rows) > 100 else None,
                        "names_unavailable": incomplete}).data)


class RegistrationStateDTO(serializers.Serializer):
    registration_id = serializers.CharField()
    topic_id = serializers.CharField()
    status = serializers.IntegerField(allow_null=True)
    point = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)


class TopicRegistrationPointView(RegistrationAPIView):
    permission_classes = [TopicGraderPermission]
    http_method_names = ["put", "options"]

    def put(self, request, topic_id, registration_id):
        dto = PointRequestDTO(data=request.data)
        dto.is_valid(raise_exception=True)
        obj = services.grade_topic_registration(
            request.auth["user_id"], request.auth["role"], topic_id, registration_id, dto.validated_data["point"],
            request.headers.get("Authorization", ""), self.request_id)
        return Response(PointResponseDTO(obj).data)


class TopicRegistrationDetailView(AdvisorReadMixin, RegistrationAPIView):
    permission_classes = [TopicManagerPermission]
    http_method_names = ["get", "delete", "head", "options"]

    def get(self, request, topic_id, registration_id):
        self.check_advisor(request, topic_id)
        obj = services.get_topic_registration(topic_id, registration_id)
        return Response(RegistrationStateDTO(obj).data)

    def delete(self, request, topic_id, registration_id):
        services.cancel_topic_registration(request.auth["user_id"], topic_id, registration_id)
        return Response(status=204)

import logging
import re
import uuid

from django.db import OperationalError
from django.shortcuts import get_object_or_404
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, BasePermission, SAFE_METHODS
from rest_framework.response import Response

from . import services
from .models import Topic
from .enrichment import topic_response
from .serializers import TopicRequestDTO

LOG = logging.getLogger(__name__)


class TopicManagementPermission(BasePermission):
    message = "Only administrators may update or delete topics; lecturers may also create topics."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.auth is not None):
            return False
        if request.method in SAFE_METHODS:
            return True
        role = request.auth.get("role")
        return type(role) is int and (role == 1 or (role == 2 and request.method == "POST"))


class HealthView(GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "topic-service"})


class TopicAPIView(GenericAPIView):
    permission_classes = [TopicManagementPermission]
    serializer_class = TopicRequestDTO

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        request_id = getattr(request, "topic_request_id", request.headers.get("X-Request-ID", ""))
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", request_id):
            request_id = uuid.uuid4().hex
        response["X-Request-ID"] = request_id
        if request.method not in SAFE_METHODS:
            LOG.info("Topic operation method=%s status=%s request_id=%s",
                     request.method, response.status_code, request_id)
        return response

    def handle_exception(self, exc):
        if isinstance(exc, OperationalError):
            exc = services.StorageUnavailable()
        return super().handle_exception(exc)

    def visible_topics(self, request):
        topics = Topic.objects.order_by("topic_id")
        role = request.auth.get("role")
        if type(role) is int and role == 2:
            topics = topics.filter(advisor_id=request.auth["user_id"])
        return topics

    def save(self, request, pk=None, partial=False):
        dto = self.get_serializer(data=request.data, partial=partial)
        dto.is_valid(raise_exception=True)
        obj = services.save_topic(dto.validated_data, str(request.auth["user_id"]),
                                  request.headers.get("Authorization", ""), pk, partial, role=request.auth["role"])
        return Response(topic_response(obj, request.headers.get("Authorization", "")),
                        status=201 if pk is None else 200)


class TopicListCreateView(TopicAPIView):
    def get(self, request):
        return Response(topic_response(self.visible_topics(request),
                                       request.headers.get("Authorization", ""), many=True))

    def post(self, request):
        return self.save(request)


class TopicDetailView(TopicAPIView):
    def get(self, request, pk):
        role = request.auth.get("role")
        return Response(topic_response(get_object_or_404(self.visible_topics(request), pk=pk), request.headers.get("Authorization", ""),
                                       management=type(role) is int and role in (1, 2)))

    def put(self, request, pk):
        return self.save(request, pk)

    def patch(self, request, pk):
        return self.save(request, pk, partial=True)

    def delete(self, request, pk):
        request_id = getattr(request, "topic_request_id", request.headers.get("X-Request-ID", ""))
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", request_id):
            request_id = uuid.uuid4().hex
        request.topic_request_id = request_id
        services.delete_topic(pk, str(request.auth["user_id"]),
                              request.headers.get("Authorization", ""), request_id)
        return Response(status=204)

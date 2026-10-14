import logging
import re
import uuid
from django.db import IntegrityError, OperationalError
from rest_framework.response import Response
from rest_framework.views import APIView
from . import services
from .models import Registration
from .permissions import StudentPermission
from .serializers import AvailableQueryDTO, AvailableResponseDTO, RegistrationFilterDTO, RegistrationRequestDTO, RegistrationResponseDTO

LOG = logging.getLogger(__name__)


def error_code(value):
    if isinstance(value, dict):
        return error_code(next(iter(value.values()), "error"))
    if isinstance(value, list):
        return error_code(value[0] if value else "error")
    return str(value)


class RegistrationAPIView(APIView):
    permission_classes = [StudentPermission]

    def initial(self, request, *args, **kwargs):
        value = request.headers.get("X-Request-ID", "")
        self.request_id = value if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) else uuid.uuid4().hex
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["X-Request-ID"] = self.request_id
        if request.method in {"POST", "PUT", "DELETE"}:
            LOG.info("Registration operation method=%s status=%s request_id=%s",
                     request.method, response.status_code, self.request_id)
        return response

    def handle_exception(self, exc):
        if isinstance(exc, OperationalError):
            exc = services.StorageUnavailable()
        elif isinstance(exc, IntegrityError):
            exc = services.RegistrationConflict("Registration references changed; refresh and try again.")
        response = super().handle_exception(exc)
        detail = response.data
        if isinstance(detail, dict) and set(detail) == {"detail"}:
            detail = detail["detail"]
        response.data = {"code": error_code(exc.get_codes()), "detail": detail}
        return response


class RegistrationListCreateView(RegistrationAPIView):
    def get(self, request):
        dto = RegistrationFilterDTO(data=request.query_params)
        dto.is_valid(raise_exception=True)
        identity = request.auth["user_id"]
        rows = Registration.objects.filter(student_id=identity)
        status = dto.validated_data.get("status")
        if status == "active":
            rows = services.current_registrations(identity)
        elif status == "cancelled":
            rows = rows.filter(status=0)
        return Response(RegistrationResponseDTO(rows, many=True).data)

    def post(self, request):
        dto = RegistrationRequestDTO(data=request.data)
        dto.is_valid(raise_exception=True)
        obj, created = services.register(request.auth["user_id"], dto.validated_data,
                                         request.headers.get("Authorization", ""), self.request_id)
        return Response(RegistrationResponseDTO(obj).data, status=201 if created else 200)


class RegistrationCancelView(RegistrationAPIView):
    def delete(self, request, pk):
        services.cancel(request.auth["user_id"], pk)
        return Response(status=204)


class AvailableTopicsView(RegistrationAPIView):
    def get(self, request):
        dto = AvailableQueryDTO(data=request.query_params)
        dto.is_valid(raise_exception=True)
        result = services.available_topics(request.auth["user_id"], dto.validated_data["after"],
                                           request.headers.get("Authorization", ""), self.request_id)
        return Response(AvailableResponseDTO(result).data)

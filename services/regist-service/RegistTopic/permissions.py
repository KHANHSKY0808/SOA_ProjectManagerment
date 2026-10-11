from rest_framework.permissions import BasePermission


class StudentPermission(BasePermission):
    message = "Only students may use registration APIs."

    def has_permission(self, request, view):
        role = request.auth.get("role") if request.auth else None
        return bool(request.user and request.user.is_authenticated and type(role) is int and role == 3)

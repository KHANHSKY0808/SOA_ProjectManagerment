from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.models import TokenUser


class RegistrationJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        identity = validated_token.get("user_id")
        if not isinstance(identity, str) or not identity.strip() or len(identity) > 255:
            raise AuthenticationFailed("Token contains no valid student identity.")
        return TokenUser(validated_token)

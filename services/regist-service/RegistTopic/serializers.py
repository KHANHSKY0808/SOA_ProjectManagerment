from rest_framework import serializers
from decimal import Decimal


class RegistrationRequestDTO(serializers.Serializer):
    topic_id = serializers.CharField(max_length=255)
    semester = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unknown or server-controlled field." for key in unknown})
        return super().to_internal_value(data)


class RegistrationResponseDTO(serializers.Serializer):
    registration_id = serializers.CharField()
    topic_id = serializers.CharField(allow_null=True)
    semester = serializers.CharField(allow_null=True)
    status = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)
    point = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)


class PointRequestDTO(serializers.Serializer):
    point = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("10"))

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - {"point"}
            if unknown:
                raise serializers.ValidationError({key: "Unknown field." for key in unknown})
        return super().to_internal_value(data)


class PointResponseDTO(serializers.Serializer):
    registration_id = serializers.CharField()
    topic_id = serializers.CharField()
    point = serializers.DecimalField(max_digits=4, decimal_places=2)
    updated_at = serializers.DateTimeField(allow_null=True)


class RegistrationFilterDTO(serializers.Serializer):
    status = serializers.ChoiceField(choices=["active", "cancelled"], required=False)


class AvailableQueryDTO(serializers.Serializer):
    after = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AvailableTopicDTO(serializers.Serializer):
    topic_id = serializers.CharField()
    name = serializers.CharField()
    major_id = serializers.CharField()
    status = serializers.IntegerField()


class AvailableResponseDTO(serializers.Serializer):
    results = AvailableTopicDTO(many=True)
    next_after = serializers.CharField(allow_null=True)

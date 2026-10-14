from rest_framework import serializers


class TopicRequestDTO(serializers.Serializer):
    topic_id = serializers.CharField(max_length=255)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    file_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    major_id = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=(0, 1, 2, 3), required=False)
    advisor_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            if "status" in data and type(data["status"]) is not int:
                raise serializers.ValidationError({"status": "Expected integer 0, 1, 2 or 3."})
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unknown or server-controlled field." for key in unknown})
        return super().to_internal_value(data)

    def validate_advisor_id(self, value):
        return value or None


class TopicResponseDTO(serializers.Serializer):
    topic_id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    file_url = serializers.CharField(read_only=True, allow_null=True)
    major_name = serializers.CharField(read_only=True, allow_null=True)
    status = serializers.IntegerField(read_only=True, allow_null=True)
    avisor_name = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True, allow_null=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    updated_by = serializers.CharField(read_only=True, allow_null=True)


class TopicManagementDetailDTO(TopicResponseDTO):
    """Reference IDs are returned only for authorized management detail reads."""

    major_id = serializers.CharField(read_only=True)
    advisor_id = serializers.CharField(read_only=True, allow_null=True)

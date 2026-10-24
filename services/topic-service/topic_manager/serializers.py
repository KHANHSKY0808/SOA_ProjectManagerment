import math
from rest_framework import serializers


class TopicRequestDTO(serializers.Serializer):
    topic_id = serializers.CharField(max_length=255)
    name = serializers.CharField()
    req_GPA = serializers.FloatField(min_value=0, max_value=4, required=False)
    studentQuota = serializers.IntegerField(min_value=1, max_value=2147483647, required=False)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    file_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    major_id = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=(0, 1, 2, 3), required=False)
    advisor_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)

    def validate_req_GPA(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Expected a finite GPA.")
        return value

    def to_internal_value(self, data):
        if isinstance(data, dict):
            for key in ("req_GPA", "studentQuota"):
                if key in data and (isinstance(data[key], bool) or not isinstance(data[key], (int, float))):
                    raise serializers.ValidationError({key: "Expected a JSON number."})
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
    req_GPA = serializers.FloatField(read_only=True)
    studentQuota = serializers.IntegerField(read_only=True)
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

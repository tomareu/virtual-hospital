from rest_framework import serializers

from patients.models import PatientRecord
from .models import RecordReport

TURNSTILE_TOKEN_MAX_LENGTH = 2048


class RecordReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordReport
        fields = [
            'record',
            'language',
            'summary',
            'diagnosis',
            'description',
            'procedures',
            'indications',
            'generated_by',
            'generated_at',
        ]


class ReportRequestSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=PatientRecord.LANGUAGE_CHOICES)
    turnstile_token = serializers.CharField(max_length=TURNSTILE_TOKEN_MAX_LENGTH)

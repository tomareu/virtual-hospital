import re

from django.db import transaction
from rest_framework import serializers
from .models import Patient, PatientRecord, RECORD_DESCRIPTION_MAX_LENGTH

ID_NUMBER_PATTERN = re.compile(r'^[A-Za-z0-9]{1,5}$')
ADMISSION_RECORD_FIELDS = ['consultation_type', 'assigned_professional', 'description', 'record_date', 'language']


class PatientRecordSerializer(serializers.ModelSerializer):
    """
    History entry for a patient (admission, edit, discharge, etc).
    """
    class Meta:
        model = PatientRecord
        fields = '__all__'


class PatientRecordCreateSerializer(serializers.ModelSerializer):
    consultation_type = serializers.ChoiceField(choices=PatientRecord.CONSULTATION_TYPE_CHOICES)
    assigned_professional = serializers.ChoiceField(choices=PatientRecord.PROFESSIONAL_CHOICES)

    class Meta:
        model = PatientRecord
        fields = [
            'consultation_type',
            'assigned_professional',
            'record_date',
            'language',
            'diagnosis',
            'description',
            'procedures',
            'indications',
        ]


class PatientSerializer(serializers.ModelSerializer):
    """
    Serializer for the patient model,
    converts python model instances into JSON for the frontend API.
    """
    avatar_style = serializers.CharField(read_only=True)

    consultation_type = serializers.ChoiceField(
        choices=PatientRecord.CONSULTATION_TYPE_CHOICES,
        write_only=True,
    )

    assigned_professional = serializers.ChoiceField(
        choices=PatientRecord.PROFESSIONAL_CHOICES,
        write_only=True,
    )

    description = serializers.CharField(write_only=True, max_length=RECORD_DESCRIPTION_MAX_LENGTH)

    record_date = serializers.DateField(write_only=True, required=False)

    language = serializers.ChoiceField(choices=PatientRecord.LANGUAGE_CHOICES, write_only=True, required=False)

    latest_record = serializers.SerializerMethodField()

    def get_latest_record(self, obj):
        records = list(obj.records.all())
        return PatientRecordSerializer(records[0]).data if records else None

    class Meta:
        model = Patient
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for validator in self.validators:
            if (
                isinstance(validator, serializers.UniqueTogetherValidator)
                and set(validator.fields) == {'location', 'id_number'}
            ):
                validator.message = (
                    'A patient with this ID already exists at this location'
                )

    def validate_id_number(self, value):
        """
        The frontend already restricts this to 1-5 alphanumeric characters
        but im double enforcing same rule here so it doesnt get bypassed 
        by any direct API call.
        
        """
        if not ID_NUMBER_PATTERN.fullmatch(value):
            raise serializers.ValidationError(
                'ID number must be 1-5 alphanumeric characters.'
            )
        return value.upper()

    def create(self, validated_data):
        """
        Admitting a patient always produces its first PatientRecord
        so both are created together in one transaction.
        """
        admission_record = {
            field: validated_data.pop(field)
            for field in ADMISSION_RECORD_FIELDS
            if field in validated_data
        }

        with transaction.atomic():
            patient = super().create(validated_data)
            PatientRecord.objects.create(patient=patient, record_type='admission', **admission_record)

        return patient
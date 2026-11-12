import secrets

from django.conf import settings
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .exceptions import RecordAlreadyComplete
from .models import Patient
from .serializers import (
    PatientSerializer,
    PatientRecordSerializer,
    PatientRecordCreateSerializer,
    PatientRecordCompleteSerializer,
)

class PatientViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows patients to be viewed or edited.
    """
    # Only return patients that are active.
    # Brings the patients records but shows only the newest.
    queryset = Patient.objects.filter(is_active=True).order_by('-created_at').prefetch_related('records')
    serializer_class = PatientSerializer

    def perform_destroy(self, instance):
        """
        Soft delete: marks the patient as inactive.
        """
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['get'])
    def records(self, request, pk=None):
        """
        Full record history for a single patient, newest first.
        """
        patient = self.get_object()
        serializer = PatientRecordSerializer(patient.records.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_record(self, request, pk=None):
        """
        Full record history for a patient, newest first.
        """
        patient = self.get_object()
        serializer = PatientRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(patient=patient, record_type='consultation')
        return Response(PatientRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path=r'records/(?P<record_id>\d+)/complete')
    def complete_record(self, request, pk=None, record_id=None):
        record = get_object_or_404(self.get_object().records, pk=record_id)
        if record.is_complete:
            raise RecordAlreadyComplete()
        serializer = PatientRecordCompleteSerializer(record, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PatientRecordSerializer(record).data)


@api_view(['GET'])
def ping(request):
    """
    No-op health check for the uptime monitor's keep-alive pings.
    """
    return Response({'status': 'ok'})


@api_view(['POST'])
def reset_sandbox(request):
    """
    Resets demo data. Requires the shared secret in X-Sandbox-Token.
    """
    token = request.headers.get('X-Sandbox-Token')
    if not settings.SANDBOX_RESET_TOKEN or not token or not secrets.compare_digest(token.encode(), settings.SANDBOX_RESET_TOKEN.encode()):
        return Response({'detail': 'Invalid token'}, status=status.HTTP_403_FORBIDDEN)

    call_command('reset_sandbox')
    return Response({'status': 'reset complete'})
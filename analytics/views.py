from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from patients.models import Patient, PatientRecord


@api_view(['GET'])
def admissions_weekly(request):
    # Admissions grouped by week, optional ?weeks=N query param, default 8.
    try:
        weeks = int(request.query_params.get('weeks', 8))
    except (TypeError, ValueError):
        weeks = 8
    weeks = max(1, min(weeks, 52))

    since = timezone.localdate() - timedelta(weeks=weeks)

    queryset = (
        PatientRecord.objects
        .filter(record_type='admission', record_date__gte=since)
        .annotate(week_start=TruncWeek('record_date'))
        .values('week_start')
        .annotate(admissions=Count('id'))
        .order_by('week_start')
    )

    data = [
        {'week_start': row['week_start'].isoformat(), 'admissions': row['admissions']}
        for row in queryset
    ]
    return Response({'period': 'weekly', 'data': data})


@api_view(['GET'])
def patients_by_species(request):
    queryset = (
        Patient.objects
        .filter(is_active=True)
        .values('species')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    data = [{'species': row['species'], 'count': row['count']} for row in queryset]
    return Response({'data': data})


@api_view(['GET'])
def consultations_by_reason(request):
    queryset = (
        PatientRecord.objects
        .exclude(consultation_type='')
        .values('consultation_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    data = [{'consultation_type': row['consultation_type'], 'count': row['count']} for row in queryset]
    return Response({'data': data})
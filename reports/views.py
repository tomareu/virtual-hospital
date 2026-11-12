from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import PatientRecord
from .documents import document_filename, issue_date, render_record, render_report
from .exceptions import RecordIncomplete
from .generation import current_report, ensure_ai_configured, generate_report
from .serializers import RecordReportSerializer, ReportRequestSerializer
from .turnstile import require_human


def get_downloadable_record(record_id):
    record = get_object_or_404(PatientRecord.objects.select_related('patient'), pk=record_id, patient__is_active=True)
    if not record.is_complete:
        raise RecordIncomplete()
    return record


def get_current_report(record_id, language):
    report = current_report(get_downloadable_record(record_id), language)
    if report is None:
        raise NotFound('This record has no up-to-date report in that language.', code='report_not_found')
    return report


def pdf_download(pdf, filename):
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


class RecordReportCreateView(APIView):

    def post(self, request, record_id):
        record = get_downloadable_record(record_id)
        serializer = ReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = serializer.validated_data['language']

        report = current_report(record, language)
        if report:
            return Response(RecordReportSerializer(report).data)

        ensure_ai_configured()
        require_human(serializer.validated_data['turnstile_token'])
        report = generate_report(record, language)
        return Response(RecordReportSerializer(report).data, status=status.HTTP_201_CREATED)


class RecordReportDetailView(APIView):

    def get(self, request, record_id, language):
        report = get_current_report(record_id, language)
        return Response(RecordReportSerializer(report).data)


class RecordReportPdfView(APIView):

    def get(self, request, record_id, language):
        report = get_current_report(record_id, language)
        pdf = render_report(report, issue_date(request.query_params.get('tz')))
        return pdf_download(pdf, document_filename(report.record, report.language))


class RecordPdfView(APIView):

    def get(self, request, record_id):
        record = get_downloadable_record(record_id)
        pdf = render_record(record, issue_date(request.query_params.get('tz')))
        return pdf_download(pdf, document_filename(record, record.language))

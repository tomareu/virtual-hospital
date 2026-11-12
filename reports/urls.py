from django.urls import path
from .views import RecordReportCreateView, RecordReportDetailView, RecordReportPdfView

urlpatterns = [
    path('records/<int:record_id>/', RecordReportCreateView.as_view(), name='record-report-create'),
    path('records/<int:record_id>/<str:language>/', RecordReportDetailView.as_view(), name='record-report-detail'),
    path('records/<int:record_id>/<str:language>/pdf/', RecordReportPdfView.as_view(), name='record-report-pdf'),
]

from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual

from patients.models import PatientRecord

SUMMARY_MAX_LENGTH = 1200
DIAGNOSIS_MAX_LENGTH = 300
DESCRIPTION_MAX_LENGTH = 1500
PROCEDURES_MAX_LENGTH = 750
INDICATIONS_MAX_LENGTH = 750


class RecordReport(models.Model):
    record = models.ForeignKey(PatientRecord, on_delete=models.CASCADE, related_name='reports')
    language = models.CharField(max_length=2, choices=PatientRecord.LANGUAGE_CHOICES)
    summary = models.TextField(max_length=SUMMARY_MAX_LENGTH)
    diagnosis = models.CharField(max_length=DIAGNOSIS_MAX_LENGTH, blank=True)
    description = models.TextField(max_length=DESCRIPTION_MAX_LENGTH)
    procedures = models.TextField(max_length=PROCEDURES_MAX_LENGTH, blank=True)
    indications = models.TextField(max_length=INDICATIONS_MAX_LENGTH, blank=True)
    source_digest = models.CharField(max_length=64, editable=False)
    generated_by = models.CharField(max_length=100)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['record', 'language'], name='unique_report_per_record_language'),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('summary'), SUMMARY_MAX_LENGTH),
                name='report_summary_max_length',
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('description'), DESCRIPTION_MAX_LENGTH),
                name='report_description_max_length',
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('procedures'), PROCEDURES_MAX_LENGTH),
                name='report_procedures_max_length',
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('indications'), INDICATIONS_MAX_LENGTH),
                name='report_indications_max_length',
            ),
        ]

    def __str__(self):
        return f"{self.get_language_display()} report — {self.record}"


class DailyTokenUsage(models.Model):
    day = models.DateField(unique=True)
    tokens = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.day}: {self.tokens} tokens"

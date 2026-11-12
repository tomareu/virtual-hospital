from datetime import datetime, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone

from board.models import BoardStroke
from patients.models import Patient, PatientRecord
from reports.models import RecordReport

SEED_MODELS = [Patient, PatientRecord, RecordReport]


def date_fields(model):
    return [field.name for field in model._meta.concrete_fields if isinstance(field, models.DateField)]


def calendar_day(value):
    return timezone.localdate(value) if isinstance(value, datetime) else value


def shift_seed_dates():
    seed = [(model, list(model.objects.all()), date_fields(model)) for model in SEED_MODELS]
    newest_day = max(
        calendar_day(getattr(obj, field))
        for _, objects, fields in seed
        for obj in objects
        for field in fields
    )
    yesterday = timezone.localdate() - timedelta(days=1)
    offset = yesterday - newest_day
    for model, objects, fields in seed:
        for obj in objects:
            for field in fields:
                setattr(obj, field, getattr(obj, field) + offset)
        model.objects.bulk_update(objects, fields)


class Command(BaseCommand):
    """Wipe demo patient data and reload the sandbox seed fixture."""

    help = "Resets the sandbox database to its seed state"

    @transaction.atomic
    def handle(self, *args, **options):
        Patient.objects.all().delete()
        BoardStroke.objects.all().delete()
        call_command('loaddata', 'sandbox_seed', stdout=self.stdout)
        shift_seed_dates()
        self.stdout.write(self.style.SUCCESS('Sandbox reset complete'))

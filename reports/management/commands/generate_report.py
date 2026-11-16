from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException

from patients.models import PatientRecord
from reports.generation import RECORD_FIELDS, current_report, generate_report


class Command(BaseCommand):
    help = 'Generates the AI report text of a record in one language'

    def add_arguments(self, parser):
        parser.add_argument('record_id', type=int)
        parser.add_argument(
            '--language',
            choices=[code for code, _ in PatientRecord.LANGUAGE_CHOICES],
            default='en',
        )
        parser.add_argument('--replace', action='store_true')

    def handle(self, *args, record_id, language, replace, **options):
        try:
            record = PatientRecord.objects.select_related('patient').get(pk=record_id)
        except PatientRecord.DoesNotExist as error:
            raise CommandError(f'Record {record_id} does not exist.') from error

        if not record.is_complete:
            raise CommandError(f'Record {record_id} is incomplete.')

        if not replace and current_report(record, language):
            raise CommandError(
                'This record already has an up-to-date report in that language. Use --replace to regenerate it.'
            )

        try:
            report = generate_report(record, language)
        except APIException as error:
            raise CommandError(str(error.detail)) from error

        for field in ['summary', *RECORD_FIELDS]:
            self.stdout.write(f'{field}: {getattr(report, field)}')

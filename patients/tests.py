import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.serializers import ValidationError
from rest_framework.test import APITestCase

from reports.models import RecordReport
from .models import (
    Patient,
    PatientRecord,
    RECORD_DESCRIPTION_MAX_LENGTH,
    RECORD_INDICATIONS_MAX_LENGTH,
    RECORD_PROCEDURES_MAX_LENGTH,
)
from .serializers import PatientSerializer

# --- Fixtures ---

PATIENT_PAYLOAD = {
    'name': 'Momo',
    'age': 3,
    'species': 'cat',
    'sex': 'female',
    'pronouns': 'she/her',
    'location': 'EA',
    'id_number': 'a12',
    'consultation_type': 'scheduled',
    'assigned_professional': 'dr_milo',
    'description': 'Admitted for a checkup.',
    'record_date': '2026-09-09',
}

RECORD_PAYLOAD = {
    'consultation_type': 'preventive',
    'assigned_professional': 'rn_tam',
    'record_date': '2026-09-10',
    'description': 'Routine follow-up.',
}

RECORD_TEXT_LIMITS = {
    'description': RECORD_DESCRIPTION_MAX_LENGTH,
    'procedures': RECORD_PROCEDURES_MAX_LENGTH,
    'indications': RECORD_INDICATIONS_MAX_LENGTH,
}

def build_patient(**overrides):
    fields = {
        'name': 'Momo',
        'age': 3,
        'species': 'cat',
        'sex': 'female',
        'pronouns': 'she/her',
        'location': 'EA',
        'id_number': 'A12',
    }
    fields.update(overrides)
    return Patient.objects.create(**fields)

def reset_sandbox_at(now):
    with patch('django.utils.timezone.now', return_value=now):
        call_command('reset_sandbox', stdout=StringIO())

def seed_days():
    return [
        *Patient.objects.order_by('pk').values_list('created_at__date', flat=True),
        *PatientRecord.objects.order_by('pk').values_list('record_date', flat=True),
        *PatientRecord.objects.order_by('pk').values_list('created_at__date', flat=True),
        *RecordReport.objects.order_by('pk').values_list('generated_at__date', flat=True),
    ]

# --- Model behaviour ---

class PatientModelTests(TestCase):

    def test_avatar_style_is_derived_from_species_and_sex(self):
        self.assertEqual(build_patient().avatar_style, 'cat_female')

    def test_unknown_species_collapses_the_whole_identity(self):
        patient = build_patient(species='unknown')
        self.assertEqual(patient.sex, 'unknown')
        self.assertEqual(patient.location, 'XX')
        self.assertEqual(patient.pronouns, 'they/them')
        self.assertEqual(patient.avatar_style, 'unknown_unknown')

    def test_unknown_location_collapses_the_whole_identity(self):
        patient = build_patient(location='XX')
        self.assertEqual(patient.species, 'unknown')
        self.assertEqual(patient.sex, 'unknown')

    def test_same_id_number_is_allowed_in_a_different_location(self):
        build_patient(location='EA', id_number='777')
        build_patient(location='PL', id_number='777')
        self.assertEqual(Patient.objects.count(), 2)

    def test_discharging_a_patient_frees_its_id_number(self):
        discharged = build_patient(id_number='777')
        discharged.is_active = False
        discharged.save()

        build_patient(id_number='777')
        self.assertEqual(Patient.objects.filter(id_number='777').count(), 2)

    def test_active_id_number_cannot_repeat_in_the_same_location(self):
        build_patient(id_number='777')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                build_patient(id_number='777')

# --- ID number validation ---

class IdNumberValidationTests(TestCase):

    def setUp(self):
        self.serializer = PatientSerializer()

    def test_id_number_is_normalised_to_uppercase(self):
        self.assertEqual(self.serializer.validate_id_number('a1b'), 'A1B')

    def test_id_number_rejects_more_than_five_characters(self):
        with self.assertRaises(ValidationError):
            self.serializer.validate_id_number('ABC123')

    def test_id_number_rejects_symbols(self):
        with self.assertRaises(ValidationError):
            self.serializer.validate_id_number('A-1')

    def test_id_number_rejects_an_empty_value(self):
        with self.assertRaises(ValidationError):
            self.serializer.validate_id_number('')

# --- Admission endpoint ---

class PatientAdmissionApiTests(APITestCase):

    url = '/api/patients/'

    def test_admitting_a_patient_creates_its_first_record(self):
        response = self.client.post(self.url, PATIENT_PAYLOAD, format='json')

        self.assertEqual(response.status_code, 201)
        patient = Patient.objects.get(id_number='A12')
        self.assertEqual(patient.records.count(), 1)

    def test_admission_record_keeps_the_date_sent_by_the_visitor(self):
        self.client.post(self.url, PATIENT_PAYLOAD, format='json')

        record = PatientRecord.objects.get(patient__id_number='A12')
        self.assertEqual(record.record_date, datetime.date(2026, 9, 9))

    def test_admission_without_a_date_uses_the_server_date(self):
        payload = {field: value for field, value in PATIENT_PAYLOAD.items() if field != 'record_date'}
        server_now = datetime.datetime(2026, 11, 12, 0, 52, tzinfo=datetime.timezone.utc)
        with patch('django.utils.timezone.now', return_value=server_now):
            self.client.post(self.url, payload, format='json')

        record = PatientRecord.objects.get(patient__id_number='A12')
        self.assertEqual(record.record_date, datetime.date(2026, 11, 12))

    def test_admission_rejects_an_invalid_date(self):
        response = self.client.post(self.url, {**PATIENT_PAYLOAD, 'record_date': '2026-13-40'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('record_date', response.data)

    def test_admission_rejects_an_invalid_id_number(self):
        response = self.client.post(
            self.url, {**PATIENT_PAYLOAD, 'id_number': 'TOOLONG'}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('id_number', response.data)

    def test_admission_rejects_a_duplicate_id_at_the_same_location(self):
        self.client.post(self.url, PATIENT_PAYLOAD, format='json')
        response = self.client.post(self.url, PATIENT_PAYLOAD, format='json')

        self.assertEqual(response.status_code, 400)

# --- Error codes ---

class ApiErrorCodeTests(APITestCase):

    url = '/api/patients/'

    def test_duplicate_id_reports_the_unique_code(self):
        self.client.post(self.url, PATIENT_PAYLOAD, format='json')
        response = self.client.post(self.url, PATIENT_PAYLOAD, format='json')

        self.assertEqual(response.data['non_field_errors'][0]['code'], 'unique')

    def test_invalid_id_number_reports_the_field_and_code(self):
        response = self.client.post(self.url, {**PATIENT_PAYLOAD, 'id_number': 'A-1'}, format='json')

        self.assertEqual(response.data['id_number'][0]['code'], 'invalid')

    def test_missing_patient_reports_the_not_found_code(self):
        response = self.client.patch(f'{self.url}9999/', {'name': 'Momo'}, format='json')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail']['code'], 'not_found')

# --- Record language ---

class RecordLanguageApiTests(APITestCase):

    def setUp(self):
        self.patient = build_patient()
        self.add_record_url = f'/api/patients/{self.patient.id}/add_record/'

    def test_consultation_keeps_the_language_it_was_written_in(self):
        self.client.post(self.add_record_url, {**RECORD_PAYLOAD, 'language': 'es'}, format='json')

        self.assertEqual(self.patient.records.get().language, 'es')

    def test_admission_keeps_the_language_it_was_written_in(self):
        self.client.post('/api/patients/', {**PATIENT_PAYLOAD, 'id_number': 'B7', 'language': 'es'}, format='json')

        self.assertEqual(PatientRecord.objects.get(patient__id_number='B7').language, 'es')

    def test_records_without_a_language_are_recorded_in_english(self):
        self.client.post(self.add_record_url, RECORD_PAYLOAD, format='json')

        self.assertEqual(self.patient.records.get().language, 'en')

    def test_unsupported_language_is_rejected(self):
        response = self.client.post(self.add_record_url, {**RECORD_PAYLOAD, 'language': 'fr'}, format='json')

        self.assertEqual(response.data['language'][0]['code'], 'invalid_choice')

# --- Record text limits ---

class RecordTextLimitApiTests(APITestCase):

    def setUp(self):
        self.patient = build_patient()
        self.add_record_url = f'/api/patients/{self.patient.id}/add_record/'

    def test_record_text_fields_accept_text_at_their_limit(self):
        payload = {**RECORD_PAYLOAD, **{field: 'x' * limit for field, limit in RECORD_TEXT_LIMITS.items()}}
        response = self.client.post(self.add_record_url, payload, format='json')

        self.assertEqual(response.status_code, 201)

    def test_record_text_fields_reject_text_over_their_limit(self):
        for field, limit in RECORD_TEXT_LIMITS.items():
            with self.subTest(field=field):
                response = self.client.post(
                    self.add_record_url, {**RECORD_PAYLOAD, field: 'x' * (limit + 1)}, format='json'
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data[field][0]['code'], 'max_length')

    def test_admission_rejects_a_description_over_the_limit(self):
        response = self.client.post(
            '/api/patients/',
            {**PATIENT_PAYLOAD, 'description': 'x' * (RECORD_DESCRIPTION_MAX_LENGTH + 1)},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['description'][0]['code'], 'max_length')


class RecordTextConstraintTests(TestCase):

    def test_database_rejects_record_text_over_its_limit(self):
        patient = build_patient()
        for field, limit in RECORD_TEXT_LIMITS.items():
            with self.subTest(field=field):
                values = {'description': 'Routine follow-up.', field: 'x' * (limit + 1)}
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        PatientRecord.objects.create(patient=patient, record_type='consultation', **values)

# --- Sandbox reset ---

RESET_NOW = datetime.datetime(2027, 3, 10, 12, 0, tzinfo=datetime.timezone.utc)

class SandboxResetTests(TestCase):

    def test_reset_moves_the_newest_seed_date_to_yesterday(self):
        reset_sandbox_at(RESET_NOW)

        self.assertEqual(max(seed_days()), datetime.date(2027, 3, 9))

    def test_reset_keeps_the_time_between_seed_dates(self):
        reset_sandbox_at(RESET_NOW)
        first_reset = seed_days()
        reset_sandbox_at(RESET_NOW + datetime.timedelta(days=10))

        self.assertEqual(seed_days(), [day + datetime.timedelta(days=10) for day in first_reset])
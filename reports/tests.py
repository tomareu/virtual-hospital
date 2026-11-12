import datetime
import json
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from patients.models import Patient, PatientRecord, RECORD_DESCRIPTION_MAX_LENGTH
from .ai import ChatCompletionClient
from .documents import (
    DEFAULT_AVATAR,
    avatar_path,
    format_date,
    issue_date,
    record_data,
    render_record,
    render_report,
    report_data,
)
from .generation import (
    MAX_COMPLETION_TOKENS,
    REASONING_EFFORT,
    RECORD_FIELDS,
    TOKEN_RESERVATION,
    build_messages,
    source_digest,
)
from .labels import LABELS
from .models import (
    DESCRIPTION_MAX_LENGTH,
    DIAGNOSIS_MAX_LENGTH,
    INDICATIONS_MAX_LENGTH,
    PROCEDURES_MAX_LENGTH,
    DailyTokenUsage,
    RecordReport,
    SUMMARY_MAX_LENGTH,
)
from .turnstile import SITEVERIFY_URL, TurnstileUnavailable, verify_token

# --- Fixtures ---

AI_SETTINGS = {
    'AI_BASE_URL': 'https://ai.test/v1',
    'AI_MODEL': 'test/model',
    'AI_API_KEY': 'test-key',
    'AI_DAILY_TOKEN_BUDGET': 10000,
    'TURNSTILE_SECRET_KEY': 'test-secret',
    'TURNSTILE_ALLOWED_HOSTNAMES': ['virtual-hospital.pages.dev'],
}

SUMMARY_TEXT = 'Momo acudió a un control de rutina y se fue de muy buen ánimo.'

REPORT_CONTENT = {
    'summary': SUMMARY_TEXT,
    'diagnosis': '',
    'description': 'Seguimiento de rutina.',
    'procedures': '',
    'indications': '',
}


def build_record(pronouns='she/her', **overrides):
    patient = Patient.objects.create(
        name='Momo', age=3, species='cat', sex='female', pronouns=pronouns, location='EA', id_number='A12'
    )
    fields = {
        'patient': patient,
        'record_type': 'consultation',
        'consultation_type': 'preventive',
        'assigned_professional': 'rn_tam',
        'description': 'Routine follow-up.',
    }
    fields.update(overrides)
    return PatientRecord.objects.create(**fields)


def create_report(record, language='es', **overrides):
    fields = {'source_digest': source_digest(record), 'generated_by': 'test/model', **REPORT_CONTENT, **overrides}
    return RecordReport.objects.create(record=record, language=language, **fields)


def report_json(**overrides):
    return json.dumps({**REPORT_CONTENT, **overrides}, ensure_ascii=False)


def completion(content=None, finish_reason='stop', total_tokens=900):
    return httpx.Response(200, json={
        'choices': [{
            'message': {'role': 'assistant', 'content': report_json() if content is None else content},
            'finish_reason': finish_reason,
        }],
        'usage': {'prompt_tokens': 600, 'completion_tokens': total_tokens - 600, 'total_tokens': total_tokens},
    })


class FakeProvider:

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.responses.pop(0)

    def client(self):
        return ChatCompletionClient(
            AI_SETTINGS['AI_BASE_URL'],
            AI_SETTINGS['AI_API_KEY'],
            AI_SETTINGS['AI_MODEL'],
            transport=httpx.MockTransport(self),
        )


def tokens_used_today():
    usage = DailyTokenUsage.objects.filter(day=timezone.now().date()).first()
    return usage.tokens if usage else 0


def rename_patient(record, name='Kiki'):
    record.patient.name = name
    record.patient.save()

# --- Report retrieval ---

class ReportRetrievalApiTests(APITestCase):

    def setUp(self):
        self.record = build_record()
        self.url = f'/api/reports/records/{self.record.id}/es/'

    def test_missing_report_reports_the_report_not_found_code(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail']['code'], 'report_not_found')

    def test_existing_report_is_returned(self):
        create_report(self.record)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary'], SUMMARY_TEXT)
        self.assertEqual(response.data['description'], 'Seguimiento de rutina.')
        self.assertEqual(response.data['generated_by'], 'test/model')

    def test_outdated_report_is_not_returned(self):
        create_report(self.record)
        rename_patient(self.record)
        response = self.client.get(self.url)
        self.assertEqual(response.data['detail']['code'], 'report_not_found')

    def test_records_of_discharged_patients_are_hidden(self):
        self.record.patient.is_active = False
        self.record.patient.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data['detail']['code'], 'not_found')

# --- Report generation ---

@override_settings(**AI_SETTINGS)
class ReportGenerationApiTests(APITestCase):

    def setUp(self):
        self.record = build_record()
        self.url = f'/api/reports/records/{self.record.id}/'
        self.payload = {'language': 'es', 'turnstile_token': 'token'}
        self.provider = FakeProvider(completion())
        self.verify = self.patch('reports.turnstile.verify_token', return_value=True)
        self.patch('reports.generation.report_client', side_effect=self.provider.client)

    def patch(self, target, **options):
        patcher = patch(target, **options)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def post_with_reply(self, content):
        self.provider.responses = [completion(content)]
        with self.assertLogs('reports.generation', level='WARNING'):
            return self.client.post(self.url, self.payload, format='json')

    def test_generation_stores_the_report_and_its_model(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary'], SUMMARY_TEXT)
        self.assertEqual(response.data['description'], 'Seguimiento de rutina.')
        report = RecordReport.objects.get(record=self.record, language='es')
        self.assertEqual(report.generated_by, 'test/model')
        self.assertEqual(report.source_digest, source_digest(self.record))

    def test_generation_requests_a_json_report_from_the_configured_model(self):
        self.client.post(self.url, self.payload, format='json')
        request = self.provider.requests[0]
        body = json.loads(request.content)
        self.assertEqual(str(request.url), 'https://ai.test/v1/chat/completions')
        self.assertEqual(request.headers['Authorization'], 'Bearer test-key')
        self.assertEqual(body['model'], 'test/model')
        self.assertEqual(body['reasoning_effort'], REASONING_EFFORT)
        self.assertEqual(body['max_completion_tokens'], MAX_COMPLETION_TOKENS)
        self.assertEqual(body['response_format']['type'], 'json_schema')
        self.assertTrue(body['response_format']['json_schema']['strict'])
        self.assertIn('Routine follow-up.', body['messages'][1]['content'])

    def test_generation_records_the_tokens_actually_used(self):
        self.client.post(self.url, self.payload, format='json')
        self.assertEqual(tokens_used_today(), 900)

    def test_current_report_skips_the_human_check_and_the_provider(self):
        create_report(self.record)
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.verify.assert_not_called()
        self.assertEqual(self.provider.requests, [])

    def test_outdated_report_is_regenerated_in_place(self):
        create_report(self.record, summary='Momo vino a control.')
        rename_patient(self.record)
        self.provider.responses = [completion(report_json(summary='Kiki vino a control.'))]
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        report = RecordReport.objects.get(record=self.record, language='es')
        self.assertEqual(report.summary, 'Kiki vino a control.')
        self.assertEqual(report.source_digest, source_digest(self.record))
        self.verify.assert_called_once()

    def test_failed_human_check_is_rejected_before_any_spending(self):
        self.verify.return_value = False
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['detail']['code'], 'turnstile_failed')
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(tokens_used_today(), 0)

    def test_unreachable_turnstile_reports_unavailable(self):
        self.verify.side_effect = TurnstileUnavailable('ConnectError')
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')

    @override_settings(AI_API_KEY=None)
    def test_missing_ai_key_reports_unavailable_without_a_human_check(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')
        self.verify.assert_not_called()

    @override_settings(TURNSTILE_SECRET_KEY=None)
    def test_missing_turnstile_secret_reports_unavailable(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')
        self.assertEqual(self.provider.requests, [])

    def test_exhausted_budget_is_rejected_without_calling_the_provider(self):
        DailyTokenUsage.objects.create(
            day=timezone.now().date(), tokens=AI_SETTINGS['AI_DAILY_TOKEN_BUDGET'] - TOKEN_RESERVATION + 1
        )
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['detail']['code'], 'report_budget_exhausted')
        self.assertEqual(self.provider.requests, [])

    def test_provider_errors_release_the_reservation(self):
        self.provider.responses = [httpx.Response(500)]
        with self.assertLogs('reports.generation', level='WARNING'):
            response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')
        self.assertEqual(tokens_used_today(), 0)

    def test_truncated_output_is_rejected_but_its_tokens_are_counted(self):
        self.provider.responses = [completion(finish_reason='length', total_tokens=1600)]
        with self.assertLogs('reports.generation', level='WARNING'):
            response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')
        self.assertFalse(RecordReport.objects.exists())
        self.assertEqual(tokens_used_today(), 1600)

    def test_malformed_replies_are_rejected(self):
        replies = {
            'not json': 'Momo is well.',
            'missing fields': json.dumps({'summary': SUMMARY_TEXT}),
            'extra fields': report_json(notes='extra'),
            'non text field': json.dumps({**REPORT_CONTENT, 'procedures': None}),
        }
        for case, content in replies.items():
            with self.subTest(case=case):
                response = self.post_with_reply(content)
                self.assertEqual(response.data['detail']['code'], 'report_unavailable')
        self.assertFalse(RecordReport.objects.exists())

    def test_replies_that_drop_or_invent_record_fields_are_rejected(self):
        replies = {
            'dropped': report_json(description=''),
            'invented': report_json(indications='Rest.'),
        }
        for case, content in replies.items():
            with self.subTest(case=case):
                response = self.post_with_reply(content)
                self.assertEqual(response.data['detail']['code'], 'report_unavailable')

    def test_blank_summary_is_rejected(self):
        response = self.post_with_reply(report_json(summary='   '))
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')

    def test_overlong_fields_are_rejected(self):
        response = self.post_with_reply(report_json(description='x' * (DESCRIPTION_MAX_LENGTH + 1)))
        self.assertEqual(response.data['detail']['code'], 'report_unavailable')

    def test_summary_whitespace_is_collapsed_into_one_paragraph(self):
        self.provider.responses = [completion(report_json(summary='  Momo está bien.\n\nPuede irse a casa.  '))]
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['summary'], 'Momo está bien. Puede irse a casa.')

    def test_record_fields_keep_their_line_breaks(self):
        self.record.description = 'Line one\nLine two'
        self.record.save()
        self.provider.responses = [completion(report_json(description='  Línea  uno \n\n Línea dos '))]
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['description'], 'Línea uno\n\nLínea dos')

    def test_output_hyphens_and_spaces_are_normalized(self):
        self.provider.responses = [completion(report_json(summary='Momo,\u202fde 2\u2011años,\u00a0está bien.'))]
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.data['summary'], 'Momo, de 2-años, está bien.')

    def test_unsupported_language_is_rejected(self):
        response = self.client.post(self.url, {**self.payload, 'language': 'fr'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['language'][0]['code'], 'invalid_choice')

    def test_missing_turnstile_token_is_rejected(self):
        response = self.client.post(self.url, {'language': 'es'}, format='json')
        self.assertEqual(response.data['turnstile_token'][0]['code'], 'required')

# --- Prompt ---

class PromptTests(TestCase):

    def test_spanish_prompt_uses_the_spanish_pronoun_mapping(self):
        record = build_record(pronouns='they/them')
        instructions = build_messages(record, 'es')[0]['content']
        self.assertIn('Spanish', instructions)
        self.assertIn('"él"', instructions)

    def test_prompt_carries_the_visit_and_every_record_field(self):
        record = build_record(diagnosis='Sneezes')
        details = json.loads(build_messages(record, 'es')[1]['content'])
        self.assertEqual(details, {
            'patient': {'name': 'Momo'},
            'visit': {'type': 'Consulta', 'category': 'Preventiva'},
            'record': {
                'diagnosis': 'Sneezes',
                'description': 'Routine follow-up.',
                'procedures': '',
                'indications': '',
            },
        })

# --- Report freshness ---

class SourceDigestTests(TestCase):

    def setUp(self):
        self.record = build_record()
        self.digest = source_digest(self.record)

    def assert_digest_after(self, instance, field, value, *, changes):
        original = getattr(instance, field)
        setattr(instance, field, value)
        with self.subTest(field=field):
            self.assertEqual(source_digest(self.record) != self.digest, changes)
        setattr(instance, field, original)

    def test_every_input_of_the_report_changes_the_digest(self):
        patient = self.record.patient
        self.assert_digest_after(patient, 'name', 'Kiki', changes=True)
        self.assert_digest_after(patient, 'pronouns', 'they/them', changes=True)
        self.assert_digest_after(self.record, 'record_type', 'admission', changes=True)
        self.assert_digest_after(self.record, 'consultation_type', 'urgent', changes=True)
        for field in RECORD_FIELDS:
            self.assert_digest_after(self.record, field, 'Changed.', changes=True)

    def test_details_rendered_outside_the_report_text_keep_the_digest(self):
        patient = self.record.patient
        self.assert_digest_after(patient, 'species', 'monkey', changes=False)
        self.assert_digest_after(patient, 'age', 9, changes=False)
        self.assert_digest_after(patient, 'location', 'PL', changes=False)
        self.assert_digest_after(self.record, 'record_date', datetime.date(2026, 1, 1), changes=False)
        self.assert_digest_after(self.record, 'assigned_professional', 'dr_milo', changes=False)

# --- Labels ---

class LabelCatalogTests(TestCase):

    def test_every_language_has_a_label_for_every_choice(self):
        choices = {
            'species': Patient.SPECIES_CHOICES,
            'sexes': Patient.SEX_CHOICES,
            'pronouns': Patient.PRONOUN_CHOICES,
            'locations': Patient.LOCATION_CHOICES,
            'record_types': PatientRecord.RECORD_TYPE_CHOICES,
            'report_titles': PatientRecord.RECORD_TYPE_CHOICES,
            'consultation_types': PatientRecord.CONSULTATION_TYPE_CHOICES,
            'professionals': PatientRecord.PROFESSIONAL_CHOICES,
        }
        self.assertEqual(set(LABELS), {code for code, _ in PatientRecord.LANGUAGE_CHOICES})
        for language, groups in LABELS.items():
            for group, group_choices in choices.items():
                with self.subTest(language=language, group=group):
                    self.assertEqual(set(groups[group]), {value for value, _ in group_choices})

    def test_every_language_has_the_same_report_text(self):
        english = LABELS['en']
        for language, labels in LABELS.items():
            with self.subTest(language=language):
                self.assertEqual(set(labels), set(english))
                self.assertEqual(set(labels['fields']), set(english['fields']))
                self.assertEqual(set(labels['report']), set(english['report']))
                self.assertEqual(len(labels['months']), 12)

# --- PDF report ---

ISSUED_ON = datetime.date(2026, 10, 29)
EVENING_IN_CHILE = datetime.datetime(2026, 10, 30, 1, 30, tzinfo=datetime.timezone.utc)


class ReportDataTests(TestCase):

    def test_spanish_report_uses_the_site_vocabulary(self):
        record = build_record(record_date=datetime.date(2026, 9, 3))
        data = report_data(create_report(record), ISSUED_ON)
        self.assertEqual(data['heading'], 'Informe de consulta')
        self.assertEqual(data['reference'], f'Registro #{record.id}')
        self.assertEqual(data['issued'], 'Fecha de emisión: 29 oct 2026')
        self.assertEqual(data['patient']['code'], 'EA-A12')
        self.assertIn(['Especie', 'Gato'], data['patient']['rows'])
        self.assertIn(['Ubicación', 'Tierra (EA)'], data['patient']['rows'])
        self.assertEqual(data['visit'], [
            ['Tipo de consulta', 'Preventiva'],
            ['Fecha', '3 sept 2026'],
            ['Profesional', 'Enf. Tam'],
        ])

    def test_english_dates_follow_the_site_format(self):
        self.assertEqual(format_date(datetime.date(2026, 10, 12), 'en'), 'Oct 12, 2026')

    def test_report_shows_the_record_in_its_own_language(self):
        record = build_record(diagnosis='Sneezes', indications='Rest at home.')
        report = create_report(record, diagnosis='Estornudos', indications='Reposo en casa.')
        data = report_data(report, ISSUED_ON)
        self.assertEqual(data['summary'], {'heading': 'Resumen', 'text': SUMMARY_TEXT})
        self.assertEqual(data['details']['rows'], [
            ['Diagnóstico', 'Estornudos'],
            ['Descripción', 'Seguimiento de rutina.'],
        ])
        self.assertEqual(data['indications'], {'heading': 'Indicaciones', 'text': 'Reposo en casa.'})

    def test_original_record_is_shown_in_its_own_language_without_a_summary(self):
        record = build_record(language='es', description='Control de rutina.', indications='Reposo en casa.')
        data = record_data(record, ISSUED_ON)
        self.assertEqual(data['heading'], 'Informe de consulta')
        self.assertIsNone(data['summary'])
        self.assertEqual(data['details']['rows'], [['Descripción', 'Control de rutina.']])
        self.assertEqual(data['indications'], {'heading': 'Indicaciones', 'text': 'Reposo en casa.'})

    def test_empty_record_fields_are_left_out(self):
        data = report_data(create_report(build_record(), language='en'), ISSUED_ON)
        self.assertIsNone(data['indications'])
        self.assertEqual([label for label, _ in data['details']['rows']], ['Description'])

    def test_issue_date_follows_the_visitor_time_zone(self):
        with patch('django.utils.timezone.now', return_value=EVENING_IN_CHILE):
            self.assertEqual(issue_date('America/Santiago'), datetime.date(2026, 10, 29))
            for name in (None, '', 'Not/AZone', '../etc/passwd', 'x' * 1000):
                with self.subTest(name=name):
                    self.assertEqual(issue_date(name), datetime.date(2026, 10, 30))

    def test_every_patient_avatar_exists(self):
        for index, (species, _) in enumerate(Patient.SPECIES_CHOICES):
            for sex, _ in Patient.SEX_CHOICES:
                patient = Patient.objects.create(
                    name='Momo', age=1, species=species, sex=sex, location='EA', id_number=f'{index}{sex[0]}'
                )
                with self.subTest(avatar=patient.avatar_style):
                    self.assertNotEqual(avatar_path(patient), DEFAULT_AVATAR)


class ReportRenderingTests(TestCase):

    def test_reports_with_every_field_at_its_limit_render(self):
        record = build_record(
            diagnosis='D' * 200,
            description='x' * RECORD_DESCRIPTION_MAX_LENGTH,
            procedures='Banana check',
            indications='Line one\nLine two',
        )
        record.patient.name = 'Ñandú 🍌'
        record.patient.save()
        for language in LABELS:
            report = create_report(
                record,
                language=language,
                summary='word ' * (SUMMARY_MAX_LENGTH // 5),
                diagnosis='D' * DIAGNOSIS_MAX_LENGTH,
                description='y' * DESCRIPTION_MAX_LENGTH,
                procedures='🍌 ñandú ' * (PROCEDURES_MAX_LENGTH // 8),
                indications='Línea\n' * (INDICATIONS_MAX_LENGTH // 6),
            )
            with self.subTest(language=language):
                self.assertTrue(render_report(report, ISSUED_ON).startswith(b'%PDF-'))

    def test_original_records_render_in_every_language(self):
        record = build_record(indications='Line one\nLine two')
        for language in LABELS:
            record.language = language
            with self.subTest(language=language):
                self.assertTrue(render_record(record, ISSUED_ON).startswith(b'%PDF-'))


class ReportPdfApiTests(APITestCase):

    def setUp(self):
        self.record = build_record()
        self.url = f'/api/reports/records/{self.record.id}/es/pdf/'

    def test_report_is_returned_as_a_pdf_download(self):
        create_report(self.record)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(
            response['Content-Disposition'], f'attachment; filename="mlvh-EA-A12-{self.record.id}-es.pdf"'
        )
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_issue_date_uses_the_tz_parameter(self):
        create_report(self.record)
        with patch('django.utils.timezone.now', return_value=EVENING_IN_CHILE), \
                patch('reports.views.render_report', return_value=b'%PDF-') as render:
            self.client.get(self.url, {'tz': 'America/Santiago'})
        self.assertEqual(render.call_args.args[1], datetime.date(2026, 10, 29))

    def test_missing_report_is_not_found(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail']['code'], 'report_not_found')

    def test_outdated_report_is_not_found(self):
        create_report(self.record)
        rename_patient(self.record)
        response = self.client.get(self.url)
        self.assertEqual(response.data['detail']['code'], 'report_not_found')

    def test_records_of_discharged_patients_are_not_found(self):
        create_report(self.record)
        self.record.patient.is_active = False
        self.record.patient.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RecordPdfApiTests(APITestCase):

    def setUp(self):
        self.record = build_record(language='es')
        self.url = f'/api/reports/records/{self.record.id}/pdf/'

    def test_original_record_downloads_in_its_own_language_without_a_report(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Disposition'], f'attachment; filename="mlvh-EA-A12-{self.record.id}-es.pdf"'
        )
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_issue_date_uses_the_tz_parameter(self):
        with patch('django.utils.timezone.now', return_value=EVENING_IN_CHILE), \
                patch('reports.views.render_record', return_value=b'%PDF-') as render:
            self.client.get(self.url, {'tz': 'America/Santiago'})
        self.assertEqual(render.call_args.args[1], datetime.date(2026, 10, 29))

    def test_records_of_discharged_patients_are_not_found(self):
        self.record.patient.is_active = False
        self.record.patient.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

# --- Turnstile ---

class TurnstileVerificationTests(TestCase):

    def verify(self, *responses, allowed=('virtual-hospital.pages.dev',)):
        self.requests = []
        pending = list(responses)

        def handler(request):
            self.requests.append(request)
            outcome = pending.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return httpx.Response(200, json=outcome)

        return verify_token('token', secret='secret', allowed_hostnames=allowed, transport=httpx.MockTransport(handler))

    def test_valid_token_from_the_site_passes(self):
        self.assertTrue(self.verify({'success': True, 'hostname': 'virtual-hospital.pages.dev'}))
        form = parse_qs(self.requests[0].content.decode())
        self.assertEqual(str(self.requests[0].url), SITEVERIFY_URL)
        self.assertEqual(form['secret'], ['secret'])
        self.assertEqual(form['response'], ['token'])

    def test_preview_deployments_pass(self):
        self.assertTrue(self.verify({'success': True, 'hostname': 'abc123.virtual-hospital.pages.dev'}))

    def test_tokens_from_other_hostnames_fail(self):
        self.assertFalse(self.verify({'success': True, 'hostname': 'evil-virtual-hospital.pages.dev'}))

    def test_unsuccessful_verification_fails(self):
        self.assertFalse(self.verify({'success': False, 'error-codes': ['invalid-input-response']}))

    def test_transport_errors_are_retried_once_with_the_same_idempotency_key(self):
        error = httpx.ConnectError('boom')
        self.assertTrue(self.verify(error, {'success': True, 'hostname': 'virtual-hospital.pages.dev'}))
        keys = [parse_qs(request.content.decode())['idempotency_key'] for request in self.requests]
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], keys[1])

    def test_persistent_transport_errors_raise_unavailable(self):
        with self.assertRaises(TurnstileUnavailable):
            self.verify(httpx.ConnectError('boom'), httpx.ConnectError('boom'))

# --- Management command ---

@override_settings(**AI_SETTINGS)
class GenerateReportCommandTests(TestCase):

    def setUp(self):
        self.record = build_record()
        self.provider = FakeProvider(completion(report_json(summary='Resumen nuevo.')))
        patcher = patch('reports.generation.report_client', side_effect=self.provider.client)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_command_generates_and_prints_the_report(self):
        output = StringIO()
        call_command('generate_report', self.record.id, language='es', stdout=output)
        self.assertIn('summary: Resumen nuevo.', output.getvalue())
        self.assertIn('description: Seguimiento de rutina.', output.getvalue())
        self.assertTrue(RecordReport.objects.filter(record=self.record, language='es').exists())

    def test_command_refuses_to_replace_a_current_report_without_the_flag(self):
        create_report(self.record)
        with self.assertRaises(CommandError):
            call_command('generate_report', self.record.id, language='es')
        self.assertEqual(self.provider.requests, [])

    def test_command_regenerates_an_outdated_report_without_the_flag(self):
        create_report(self.record)
        rename_patient(self.record)
        call_command('generate_report', self.record.id, language='es', stdout=StringIO())
        report = RecordReport.objects.get(record=self.record, language='es')
        self.assertEqual(report.summary, 'Resumen nuevo.')

    def test_replace_regenerates_the_current_report(self):
        create_report(self.record, generated_by='old/model')
        call_command('generate_report', self.record.id, language='es', replace=True, stdout=StringIO())
        report = RecordReport.objects.get(record=self.record, language='es')
        self.assertEqual(report.summary, 'Resumen nuevo.')
        self.assertEqual(report.generated_by, 'test/model')

# --- Sandbox reset ---

class SandboxResetTests(TestCase):

    def test_reset_removes_reports_but_keeps_token_usage(self):
        create_report(build_record())
        DailyTokenUsage.objects.create(day=timezone.now().date(), tokens=1234)
        call_command('reset_sandbox', stdout=StringIO())
        self.assertFalse(RecordReport.objects.exists())
        self.assertEqual(tokens_used_today(), 1234)

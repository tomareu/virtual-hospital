import json
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typst
from django.conf import settings
from django.utils import timezone

from .labels import LABELS

PDF_DIR = Path(__file__).resolve().parent / 'pdf'
FONTS_DIR = PDF_DIR / 'fonts'
ASSETS_DIR = settings.BASE_DIR / 'frontend' / 'assets'
DEFAULT_AVATAR = '/default-avatar.png'
PDF_STANDARDS = ['a-2a', 'ua-1']


@cache
def report_template():
    return (PDF_DIR / 'report.typ').read_bytes()


def issue_date(time_zone_name):
    try:
        zone = ZoneInfo(time_zone_name)
    except (TypeError, ValueError, OSError, ZoneInfoNotFoundError):
        zone = None
    return timezone.localdate(timezone=zone)


def format_date(value, language):
    labels = LABELS[language]
    return labels['date_format'].format(day=value.day, month=labels['months'][value.month - 1], year=value.year)


def avatar_path(patient):
    path = f'/avatars/{patient.avatar_style}.png'
    return path if (ASSETS_DIR / path.lstrip('/')).is_file() else DEFAULT_AVATAR


def patient_code(patient):
    return f'{patient.location}-{patient.id_number}'


def section(heading, text):
    return {'heading': heading, 'text': text}


def report_data(report, issued_on):
    return document_data(report.record, report.language, report, report.summary, issued_on)


def record_data(record, issued_on):
    return document_data(record, record.language, record, None, issued_on)


def document_data(record, language, content, summary, issued_on):
    patient = record.patient
    labels = LABELS[language]
    fields = labels['fields']
    text = labels['report']
    code = patient_code(patient)
    heading = labels['report_titles'][record.record_type]
    visit = [
        (fields['consultation_type'], labels['consultation_types'].get(record.consultation_type)),
        (fields['date'], format_date(record.record_date, language)),
        (fields['professional'], labels['professionals'].get(record.assigned_professional)),
    ]
    details = [
        (fields['diagnosis'], content.diagnosis),
        (fields['description'], content.description),
        (fields['procedures'], content.procedures),
    ]
    return {
        'language': language,
        'document_title': f'{heading} · {patient.name} [{code}]',
        'heading': heading,
        'reference': text['reference'].format(id=record.id),
        'issued': text['issued'].format(date=format_date(issued_on, language)),
        'patient': {
            'name': patient.name,
            'code': code,
            'avatar': avatar_path(patient),
            'avatar_alt': text['avatar_alt'].format(name=patient.name),
            'rows': [
                [fields['species'], labels['species'][patient.species]],
                [fields['sex'], labels['sexes'][patient.sex]],
                [fields['pronouns'], labels['pronouns'][patient.pronouns]],
                [fields['age'], str(patient.age)],
                [fields['location'], labels['locations'][patient.location]],
            ],
        },
        'visit': [[label, value] for label, value in visit if value],
        'summary': section(text['summary'], summary) if summary else None,
        'details': {
            'heading': text['details'],
            'rows': [[label, value] for label, value in details if value],
        },
        'indications': section(fields['indications'], content.indications) if content.indications else None,
        'footer': text['footer'],
    }


def render_document(data):
    return typst.compile(
        report_template(),
        root=str(ASSETS_DIR),
        font_paths=[str(FONTS_DIR)],
        ignore_system_fonts=True,
        sys_inputs={'data': json.dumps(data, ensure_ascii=False)},
        pdf_standards=PDF_STANDARDS,
    )


def render_report(report, issued_on):
    return render_document(report_data(report, issued_on))


def render_record(record, issued_on):
    return render_document(record_data(record, issued_on))


def document_filename(record, language):
    return f'mlvh-{patient_code(record.patient)}-{record.id}-{language}.pdf'

from django.db import migrations
from django.db.models.functions import Length, Substr
from django.db.models.lookups import GreaterThan

RECORD_TEXT_LIMITS = {
    'description': 1000,
    'procedures': 500,
    'indications': 500,
}


def truncate_record_text(apps, schema_editor):
    PatientRecord = apps.get_model('patients', 'PatientRecord')
    for field, limit in RECORD_TEXT_LIMITS.items():
        PatientRecord.objects.filter(GreaterThan(Length(field), limit)).update(
            **{field: Substr(field, 1, limit)}
        )


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0010_alter_patientrecord_assigned_professional'),
    ]

    operations = [
        migrations.RunPython(truncate_record_text, migrations.RunPython.noop, elidable=True),
    ]
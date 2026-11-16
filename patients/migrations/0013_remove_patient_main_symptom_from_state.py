from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0012_record_text_max_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='main_symptom',
            field=models.CharField(blank=True, db_default='', max_length=200),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='patient',
                    name='main_symptom',
                ),
            ],
        ),
    ]
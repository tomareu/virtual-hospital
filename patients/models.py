from django.db import models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual
from django.utils import timezone

RECORD_DESCRIPTION_MAX_LENGTH = 1000
RECORD_PROCEDURES_MAX_LENGTH = 500
RECORD_INDICATIONS_MAX_LENGTH = 500

class Patient(models.Model):
    """
    Basic patient model for MLVH
    Replaces standard clinical data with a playful, RPG style structure!
    """
    SPECIES_CHOICES = [
        ('human', 'Human'),
        ('cat', 'Cat'),
        ('bunny', 'Bunny'),
        ('rat', 'Rat'),
        ('monkey', 'Monkey'),
        ('unknown', 'Unknown'),
    ]

    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('unknown', 'Unknown'),
    ]

    PRONOUN_CHOICES = [
        ('she/her', 'She/Her'),
        ('he/him', 'He/Him'),
        ('they/them', 'They/Them'),
    ]

    LOCATION_CHOICES = [
        ('EA', 'Earth'),
        ('PL', 'Pluto'),
        ('ET', 'Ether'),
        ('NW', 'Nowhere'),
        ('XX', 'Unknown'),
    ]

    # Core character stats
    name = models.CharField(max_length=20)
    age = models.PositiveIntegerField()
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES, default='human')
    sex = models.CharField(max_length=20, choices=SEX_CHOICES, default='unknown')
    pronouns = models.CharField(max_length=20, choices=PRONOUN_CHOICES, default='they/them')

    # Composite patient ID + location acting as the prefix (e.g.,'EA-99999')
    location = models.CharField(max_length=2, choices=LOCATION_CHOICES, default='EA')
    id_number = models.CharField(max_length=5)

    avatar_style = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Flag for soft-delete
    is_active = models.BooleanField(default=True)

    class Meta:
        # id_number is only meaningful scoped to its location
        # (e.g. 'EA-2222' and 'PL-2222' r different patients)
        constraints = [
            models.UniqueConstraint(
                fields=['location', 'id_number'],
                condition=models.Q(is_active=True),
                name='unique_active_patient_id_per_location',
            )
        ]

    def __str__(self):
        return f"[{self.location}-{self.id_number}] {self.name} the {self.species.capitalize()}"

    def save(self, *args, **kwargs):
        """
        Auto-generate the avatar style based on the selected species and sex.
        Enforces the "unknown" character as a single, indivisible unit:
        sex, species, location and pronouns only ever move to their unknown
        value together. :D
        """
        if self.sex == 'unknown' or self.species == 'unknown' or self.location == 'XX':
            self.sex = 'unknown'
            self.species = 'unknown'
            self.location = 'XX'
            self.pronouns = 'they/them'

        self.avatar_style = f"{self.species}_{self.sex}"
        super().save(*args, **kwargs)


class PatientRecord(models.Model):
    """
    A single entry in a patients timeline, something that happened to them 
    (admission, profile edit, discharge etc). basically, lastest record. 
    """
    RECORD_TYPE_CHOICES = [
        ('admission', 'Admission'),
        ('consultation', 'Consultation'),
    ]

    CONSULTATION_TYPE_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('preventive', 'Preventive'),
        ('urgent', 'Urgent'),
    ]

    # im not creating staff accounts yet, so professionals will only be these now
    PROFESSIONAL_CHOICES = [
        ('dr_milo', 'Dr. Milo'),
        ('rn_tam', 'RN. Tam'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='records')
    record_type = models.CharField(max_length=20, choices=RECORD_TYPE_CHOICES)
    consultation_type = models.CharField(max_length=20, choices=CONSULTATION_TYPE_CHOICES, blank=True)
    assigned_professional = models.CharField(max_length=20, choices=PROFESSIONAL_CHOICES, blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='en')

    # Date the consultation actually took place, editable by whoever logs it
    record_date = models.DateField(default=timezone.localdate)

    diagnosis = models.CharField(max_length=200, blank=True)
    procedures = models.TextField(max_length=RECORD_PROCEDURES_MAX_LENGTH, blank=True)
    indications = models.TextField(max_length=RECORD_INDICATIONS_MAX_LENGTH, blank=True)

    # Future records tab reads and displays
    description = models.TextField(max_length=RECORD_DESCRIPTION_MAX_LENGTH)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('description'), RECORD_DESCRIPTION_MAX_LENGTH),
                name='record_description_max_length',
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('procedures'), RECORD_PROCEDURES_MAX_LENGTH),
                name='record_procedures_max_length',
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length('indications'), RECORD_INDICATIONS_MAX_LENGTH),
                name='record_indications_max_length',
            ),
        ]

    def __str__(self):
        return f"{self.get_record_type_display()} — {self.patient}"
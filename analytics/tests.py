from rest_framework.test import APITestCase

from patients.models import Patient, PatientRecord


class AnalyticsPayloadTests(APITestCase):

    def setUp(self):
        patient = Patient.objects.create(
            name='Momo', age=3, species='cat', sex='female', pronouns='she/her', location='EA', id_number='A12',
        )
        PatientRecord.objects.create(
            patient=patient, record_type='consultation', consultation_type='urgent', description='Cough',
        )

    def test_patients_by_species_sends_values_only(self):
        response = self.client.get('/api/analytics/patients-by-species/')
        self.assertEqual(response.data['data'], [{'species': 'cat', 'count': 1}])

    def test_consultations_by_reason_sends_values_only(self):
        response = self.client.get('/api/analytics/consultations-by-reason/')
        self.assertEqual(response.data['data'], [{'consultation_type': 'urgent', 'count': 1}])

    def test_consultations_by_reason_counts_the_first_consultation(self):
        PatientRecord.objects.create(
            patient=Patient.objects.get(), record_type='admission', consultation_type='scheduled', description='Check-up',
        )

        response = self.client.get('/api/analytics/consultations-by-reason/')

        self.assertCountEqual(response.data['data'], [
            {'consultation_type': 'urgent', 'count': 1},
            {'consultation_type': 'scheduled', 'count': 1},
        ])
from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone

from incidents.models import IncidentSequence
from incidents.services.routing import RoutingError, generate_incident_id, validate_three_different_people
from incidents.services.workflow import is_late_at_submission
from incidents.tests.helpers import make_user


class RoutingTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter")
        self.verifier = make_user("verifier")
        self.approver = make_user("approver")

    def test_validate_three_different_people_ok(self):
        validate_three_different_people(self.reporter, self.verifier, self.approver)

    def test_validate_rejects_duplicate_participants(self):
        with self.assertRaises(RoutingError):
            validate_three_different_people(self.reporter, self.reporter, self.approver)

    def test_generate_incident_id_format(self):
        submitted = timezone.make_aware(datetime(2026, 7, 15, 10, 30))
        incident_id = generate_incident_id(submitted)
        self.assertEqual(incident_id, "0726001")

    def test_generate_incident_id_increments_monthly(self):
        submitted = timezone.make_aware(datetime(2026, 7, 1, 8, 0))
        self.assertEqual(generate_incident_id(submitted), "0726001")
        self.assertEqual(generate_incident_id(submitted), "0726002")

    def test_generate_incident_id_resets_each_month(self):
        july = timezone.make_aware(datetime(2026, 7, 31, 23, 0))
        august = timezone.make_aware(datetime(2026, 8, 1, 8, 0))
        self.assertEqual(generate_incident_id(july), "0726001")
        self.assertEqual(generate_incident_id(august), "0826001")

    def test_generate_incident_id_monthly_limit(self):
        IncidentSequence.objects.create(period="202607", last_sequence=999)
        submitted = timezone.make_aware(datetime(2026, 7, 9, 12, 0))
        with self.assertRaises(RoutingError):
            generate_incident_id(submitted)

    def test_late_submission_after_threshold(self):
        incident_date = date(2026, 7, 9)
        incident_time = time(9, 0)
        submitted_at = timezone.make_aware(datetime(2026, 7, 9, 9, 31))
        self.assertTrue(is_late_at_submission(incident_date, incident_time, submitted_at))

    def test_late_submission_exactly_at_threshold_not_late(self):
        incident_date = date(2026, 7, 9)
        incident_time = time(9, 0)
        submitted_at = timezone.make_aware(datetime(2026, 7, 9, 9, 30))
        self.assertFalse(is_late_at_submission(incident_date, incident_time, submitted_at))

    def test_late_submission_missing_datetime(self):
        self.assertFalse(is_late_at_submission(None, None))

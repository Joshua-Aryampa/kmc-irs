from accounts.models import Role
from django.test import TestCase

from incidents.models import IncidentStatus
from incidents.tests.helpers import make_incident, make_user


class IncidentModelTests(TestCase):
    def test_full_name_and_role_helpers(self):
        user = make_user("worker", role=Role.WORKER)
        self.assertEqual(user.full_name, "Worker User")
        self.assertTrue(user.can_report())
        self.assertFalse(user.has_plant_wide_access())

        admin = make_user("admin", role=Role.ADMIN)
        self.assertFalse(admin.can_report())
        self.assertTrue(admin.has_plant_wide_access())

    def test_incident_editability_and_labels(self):
        reporter = make_user("reporter")
        incident = make_incident(
            reporter,
            status=IncidentStatus.DRAFT,
            involves_person=True,
            involves_product=True,
            classification_injury=True,
            classification_breakdown=True,
            other_person=True,
            other_person_text="Contractor",
        )
        self.assertTrue(incident.is_editable_by_reporter)
        self.assertFalse(incident.is_closed)
        self.assertIn("Person(s)", incident.involves_labels())
        self.assertIn("Injury", incident.classification_labels())
        self.assertIn("Person(s) Other (Contractor)", incident.classification_labels())

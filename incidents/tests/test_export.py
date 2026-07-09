from django.test import TestCase

from incidents.models import Incident, IncidentStatus
from incidents.services.export import incidents_csv
from incidents.tests.helpers import make_incident, make_user


class ExportTests(TestCase):
    def test_incidents_csv_contains_header_and_row(self):
        reporter = make_user("reporter")
        verifier = make_user("verifier")
        incident = make_incident(
            reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=verifier,
            incident_id="0726001",
        )
        response = incidents_csv(Incident.objects.filter(pk=incident.pk))
        content = response.content.decode("utf-8")
        self.assertIn("Incident ID", content)
        self.assertIn("0726001", content)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="incidents_export.csv"')

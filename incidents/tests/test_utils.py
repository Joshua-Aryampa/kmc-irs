from datetime import date

from django.test import RequestFactory, TestCase

from incidents.models import Incident, IncidentStatus, Severity
from incidents.tests.helpers import make_incident, make_user
from incidents.utils import apply_incident_filters, filter_form_values, incident_summary, paginate_queryset


class UtilsTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter")
        self.verifier = make_user("verifier")
        self.approver = make_user("approver")

    def test_apply_incident_filters(self):
        open_incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
            severity=Severity.MINOR,
            incident_date=date(2026, 7, 1),
            is_late_submission=True,
        )
        closed_incident = make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            severity=Severity.MAJOR,
            incident_date=date(2026, 6, 1),
        )
        qs = apply_incident_filters(
            Incident.objects.all(),
            {
                "status": IncidentStatus.PENDING_VERIFICATION,
                "severity": Severity.MINOR,
                "late": "1",
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            },
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, open_incident.pk)
        self.assertNotIn(closed_incident.pk, list(qs.values_list("pk", flat=True)))

    def test_filter_form_values(self):
        values = filter_form_values(
            {"status": "CLOSED", "severity": "MINOR", "date_from": "2026-01-01", "late": "1"}
        )
        self.assertEqual(values["status"], "CLOSED")
        self.assertEqual(values["severity"], "MINOR")

    def test_incident_summary(self):
        make_incident(self.reporter, status=IncidentStatus.PENDING_VERIFICATION, verifier=self.verifier)
        make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            is_late_submission=True,
        )
        summary = incident_summary(Incident.objects.all())
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["closed"], 1)
        self.assertEqual(summary["pending_verification"], 1)
        self.assertEqual(summary["late"], 1)

    def test_paginate_queryset(self):
        for index in range(3):
            make_incident(self.reporter, scene_location=f"Area {index}")
        factory = RequestFactory()
        request = factory.get("/history/")
        page = paginate_queryset(request, Incident.objects.all(), per_page=2)
        self.assertEqual(len(page.object_list), 2)

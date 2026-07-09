from unittest.mock import patch

from django.test import RequestFactory, TestCase

from accounts.models import Role
from incidents.context_processors import nav_counts
from incidents.models import Incident, IncidentStatus, Severity
from incidents.services import pdf as pdf_service
from incidents.tests.helpers import add_photo, add_witness, make_incident, make_user


class ViewTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter", keycloak_id="kc-reporter")
        self.verifier = make_user("verifier", keycloak_id="kc-verifier")
        self.approver = make_user("approver", keycloak_id="kc-approver")
        self.admin = make_user("admin", role=Role.ADMIN)
        self.client.defaults["HTTP_HOST"] = "testserver"

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_dashboard_for_reporter(self):
        self.client.login(username="reporter", password="testpass123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_admin_cannot_open_create_form(self):
        self.client.login(username="admin", password="testpass123")
        response = self.client.get("/incidents/new/")
        self.assertEqual(response.status_code, 302)

    def test_incident_detail_hides_other_users_draft(self):
        draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        self.client.login(username="admin", password="testpass123")
        response = self.client.get(f"/incidents/{draft.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_delete_draft_allowed_for_reporter(self):
        draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        self.client.login(username="reporter", password="testpass123")
        response = self.client.post(f"/incidents/{draft.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Incident.objects.filter(pk=draft.pk).exists())

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_approver")
    @patch("incidents.services.workflow.notify_closed")
    def test_verify_and_approve_actions(self, _notify_closed, _notify_approve, _signature_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self.client.login(username="verifier", password="testpass123")
        verify_response = self.client.post(
            f"/incidents/{incident.pk}/verify/",
            {
                "severity": Severity.MINOR,
                "approver_keycloak_id": self.approver.keycloak_id,
                "approver_name": self.approver.full_name,
            },
        )
        self.assertEqual(verify_response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.PENDING_APPROVAL)

        self.client.login(username="approver", password="testpass123")
        approve_response = self.client.post(f"/incidents/{incident.pk}/approve/")
        self.assertEqual(approve_response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.CLOSED)

    def test_approve_rejects_get_request(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_APPROVAL,
            verifier=self.verifier,
            approver=self.approver,
        )
        self.client.login(username="approver", password="testpass123")
        response = self.client.get(f"/incidents/{incident.pk}/approve/")
        self.assertEqual(response.status_code, 405)

    def test_history_csv_export(self):
        make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            incident_id="0726001",
        )
        self.client.login(username="reporter", password="testpass123")
        response = self.client.get("/history/?export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(b"0726001", response.content)

    def test_employee_search_api(self):
        self.client.login(username="reporter", password="testpass123")
        response = self.client.get("/api/employees/search/?q=ver")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["name"] == "Verifier User" for item in payload["results"]))

    def test_closed_incident_pdf_download(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            incident_id="0726001",
            severity=Severity.MINOR,
        )
        add_witness(incident)
        add_photo(incident)
        self.client.login(username="reporter", password="testpass123")
        response = self.client.get(f"/incidents/{incident.pk}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_nav_counts_context_processor(self):
        make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.verifier
        request.session = {}
        context = nav_counts(request)
        self.assertEqual(context["nav_counts"]["queue_verify"], 1)

    @patch("incidents.services.pdf.render_to_string", return_value="<html><body>Report</body></html>")
    def test_pdf_service_render(self, _render_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            incident_id="0726001",
        )
        factory = RequestFactory()
        request = factory.get("/")
        pdf_bytes = pdf_service.render_incident_pdf(request, incident)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

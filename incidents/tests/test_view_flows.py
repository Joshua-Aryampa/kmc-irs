from unittest.mock import patch

from django.test import TestCase

from accounts.models import Role
from incidents.models import Incident, IncidentStatus, Severity
from incidents.tests.helpers import (
    add_photo,
    add_witness,
    base_incident_post_data,
    make_incident,
    make_test_image,
    make_user,
    witness_formset_management,
    witness_row,
)


class IncidentViewFlowTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter", keycloak_id="kc-reporter")
        self.verifier = make_user("verifier", keycloak_id="kc-verifier")
        self.approver = make_user("approver", keycloak_id="kc-approver")
        self.other = make_user("other", keycloak_id="kc-other")

    def _login(self, username):
        self.assertTrue(self.client.login(username=username, password="testpass123"))

    def test_login_page_renders_without_keycloak(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_queue_page_lists_assigned_items(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
            incident_id="0726099",
        )
        self._login("verifier")
        response = self.client.get("/queue/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending my verification")
        self.assertContains(response, "0726099")

    def test_queue_all_tab_lists_items_with_unrelated_page_param(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
            incident_id="0726100",
        )
        self._login("verifier")
        response = self.client.get("/queue/?page_verify=99")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0726100")

    def test_history_page_and_filters(self):
        make_incident(
            self.reporter,
            status=IncidentStatus.CLOSED,
            verifier=self.verifier,
            approver=self.approver,
            incident_id="0726001",
        )
        self._login("reporter")
        response = self.client.get("/history/?status=CLOSED")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0726001")

    def test_create_incident_get(self):
        self._login("reporter")
        response = self.client.get("/incidents/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New incident")

    def test_edit_draft_get(self):
        draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        self._login("reporter")
        response = self.client.get(f"/incidents/{draft.pk}/edit/")
        self.assertEqual(response.status_code, 200)

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_submitted")
    def test_submit_incident_via_create(self, _notify, _signature):
        self._login("reporter")
        data = base_incident_post_data()
        data.update(
            {
                "action": "submit",
                "confirm": "on",
                "verifier_keycloak_id": self.verifier.keycloak_id,
                "verifier_name": self.verifier.full_name,
            }
        )
        data.update(witness_formset_management())
        data.update(
            witness_row(
                index=0,
                keycloak_id=self.other.keycloak_id,
                name=self.other.full_name,
            )
        )
        response = self.client.post(
            "/incidents/new/",
            {**data, "photos": make_test_image()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 302, response.content.decode()[:800])
        incident = Incident.objects.get(reporter=self.reporter, status=IncidentStatus.PENDING_VERIFICATION)
        self.assertTrue(incident.incident_id)

    def test_incident_detail_for_submitted_incident(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
            incident_id="0726002",
        )
        self._login("reporter")
        response = self.client.get(f"/incidents/{incident.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0726002")

    def test_reject_verification_returns_to_reporter(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self._login("verifier")
        response = self.client.post(
            f"/incidents/{incident.pk}/reject-verify/",
            {"comment": "Please add more detail to the report."},
        )
        self.assertEqual(response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_REPORTER)

    @patch("incidents.services.workflow.notify_reporter_returned")
    def test_forward_to_reporter_from_verifier(self, _notify_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.RETURNED_TO_VERIFIER,
            verifier=self.verifier,
        )
        self._login("verifier")
        response = self.client.post(
            f"/incidents/{incident.pk}/forward/",
            {"comment": "Please correct the report and resubmit."},
        )
        self.assertEqual(response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_REPORTER)

    def test_reject_approval_returns_to_verifier(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_APPROVAL,
            verifier=self.verifier,
            approver=self.approver,
        )
        self._login("approver")
        response = self.client.post(
            f"/incidents/{incident.pk}/reject-approve/",
            {"comment": "Verifier should review this again please."},
        )
        self.assertEqual(response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_VERIFIER)

    def test_pdf_redirects_when_incident_not_closed(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self._login("reporter")
        response = self.client.get(f"/incidents/{incident.pk}/pdf/")
        self.assertEqual(response.status_code, 302)

    def test_photo_delete_requires_post(self):
        incident = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        add_photo(incident)
        add_photo(incident)
        photo = incident.photos.first()
        self._login("reporter")
        response = self.client.get(f"/incidents/{incident.pk}/photos/{photo.pk}/delete/")
        self.assertEqual(response.status_code, 405)

    def test_photo_delete_removes_photo(self):
        incident = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        add_photo(incident)
        add_photo(incident)
        photo = incident.photos.first()
        self._login("reporter")
        response = self.client.post(f"/incidents/{incident.pk}/photos/{photo.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(incident.photos.count(), 1)

    def test_edit_draft_get(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
            incident_id="0726002",
        )
        self._login("reporter")
        response = self.client.get(f"/incidents/{incident.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0726002")

    def test_reject_verify_requires_comment(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self._login("verifier")
        response = self.client.post(f"/incidents/{incident.pk}/reject-verify/", {"comment": "short"})
        self.assertEqual(response.status_code, 302)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.PENDING_VERIFICATION)

    def test_other_user_cannot_edit_draft(self):
        draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        self._login("other")
        response = self.client.get(f"/incidents/{draft.pk}/edit/")
        self.assertEqual(response.status_code, 403)

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_submitted")
    @patch("incidents.services.workflow.notify_approver")
    @patch("incidents.services.workflow.notify_closed")
    def test_full_submit_verify_approve_via_services_setup(
        self, _closed, _approver_notify, _submit_notify, _sig
    ):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self._login("verifier")
        self.client.post(
            f"/incidents/{incident.pk}/verify/",
            {
                "severity": Severity.MINOR,
                "approver_keycloak_id": self.approver.keycloak_id,
                "approver_name": self.approver.full_name,
            },
        )
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.PENDING_APPROVAL)
        self._login("approver")
        self.client.post(f"/incidents/{incident.pk}/approve/")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.CLOSED)

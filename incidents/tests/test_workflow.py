from datetime import timedelta

from django.utils import timezone
from unittest.mock import patch

from django.test import TestCase

from incidents.models import IncidentStatus, NotificationLog, Severity, TimelineEntryType
from incidents.services.workflow import (
    WorkflowError,
    approve_incident,
    forward_to_reporter,
    reject_approval,
    reject_verification,
    submit_incident,
    verify_incident,
)
from incidents.tests.helpers import make_incident, make_user


class WorkflowTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter")
        self.verifier = make_user("verifier")
        self.approver = make_user("approver")

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_submitted")
    def test_submit_incident(self, notify_mock, signature_mock):
        incident = make_incident(self.reporter)
        submit_incident(incident, self.reporter, self.verifier)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.PENDING_VERIFICATION)
        self.assertEqual(incident.verifier_id, self.verifier.id)
        self.assertTrue(incident.incident_id)
        notify_mock.assert_called_once()
        signature_mock.assert_called_once()

    def test_submit_requires_verifier(self):
        incident = make_incident(self.reporter)
        with self.assertRaises(WorkflowError):
            submit_incident(incident, self.reporter, None)

    def test_submit_rejects_same_person_as_verifier(self):
        incident = make_incident(self.reporter)
        with self.assertRaises(WorkflowError):
            submit_incident(incident, self.reporter, self.reporter)

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_approver")
    def test_verify_incident(self, notify_mock, signature_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        verify_incident(incident, self.verifier, Severity.MINOR, self.approver)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.PENDING_APPROVAL)
        self.assertEqual(incident.approver_id, self.approver.id)
        notify_mock.assert_called_once()

    @patch("incidents.services.workflow.notify_reporter_returned")
    def test_reject_verification(self, notify_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        reject_verification(incident, self.verifier, "Needs more detail.")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_REPORTER)
        self.assertEqual(incident.return_comment, "Needs more detail.")
        notify_mock.assert_called_once()

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_closed")
    def test_approve_incident(self, notify_mock, signature_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_APPROVAL,
            verifier=self.verifier,
            approver=self.approver,
        )
        approve_incident(incident, self.approver)
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.CLOSED)
        self.assertIsNotNone(incident.closed_at)
        notify_mock.assert_called_once()

    @patch("incidents.services.workflow.notify_verifier_rejected_by_approver")
    def test_reject_approval(self, notify_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_APPROVAL,
            verifier=self.verifier,
            approver=self.approver,
        )
        reject_approval(incident, self.approver, "Please review again.")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_VERIFIER)
        notify_mock.assert_called_once()

    @patch("incidents.services.workflow.notify_reporter_returned")
    def test_forward_to_reporter(self, notify_mock):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.RETURNED_TO_VERIFIER,
            verifier=self.verifier,
            pending_approver_comment="Approver comment",
        )
        forward_to_reporter(incident, self.verifier, "Please correct the report.")
        incident.refresh_from_db()
        self.assertEqual(incident.status, IncidentStatus.RETURNED_TO_REPORTER)
        notify_mock.assert_called_once()

    def test_submit_creates_timeline_entry(self):
        incident = make_incident(self.reporter)
        with patch("incidents.services.workflow.attach_signature"), patch(
            "incidents.services.workflow.notify_submitted"
        ):
            submit_incident(incident, self.reporter, self.verifier)
        self.assertTrue(
            incident.timeline_entries.filter(entry_type=TimelineEntryType.SUBMITTED).exists()
        )

    @patch("incidents.services.workflow.attach_signature")
    def test_late_submission_requires_reason(self, _signature_mock):
        incident = make_incident(
            self.reporter,
            late_reason="",
        )
        incident.incident_date = timezone.localdate()
        incident.incident_time = (timezone.localtime() - timedelta(hours=2)).time().replace(second=0, microsecond=0)
        incident.save()
        with self.assertRaises(WorkflowError):
            submit_incident(incident, self.reporter, self.verifier)

    @patch("incidents.services.workflow.attach_signature")
    @patch("incidents.services.workflow.notify_submitted")
    def test_late_submission_with_reason(self, _notify, _signature_mock):
        incident = make_incident(self.reporter, late_reason="Shift handover delayed report.")
        incident.incident_date = timezone.localdate()
        incident.incident_time = (timezone.localtime() - timedelta(hours=2)).time().replace(second=0, microsecond=0)
        incident.save()
        submit_incident(incident, self.reporter, self.verifier)
        incident.refresh_from_db()
        self.assertTrue(incident.is_late_submission)

    @patch("incidents.services.notifications.send_mail")
    def test_notification_log_created_on_submit(self, send_mail_mock):
        send_mail_mock.return_value = 1
        self.verifier.email = "verifier@test.local"
        self.verifier.save(update_fields=["email"])
        incident = make_incident(self.reporter)
        with patch("incidents.services.workflow.attach_signature"):
            submit_incident(incident, self.reporter, self.verifier)
        self.assertEqual(NotificationLog.objects.filter(incident=incident).count(), 1)

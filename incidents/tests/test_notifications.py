from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from incidents.models import NotificationLog
from incidents.services import notifications
from incidents.tests.helpers import make_incident, make_user


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter", email="reporter@test.local")
        self.verifier = make_user("verifier", email="verifier@test.local")
        self.approver = make_user("approver", email="approver@test.local")

    def test_notify_submitted_sends_email_and_logs_success(self):
        incident = make_incident(
            self.reporter,
            incident_id="0726001",
            verifier=self.verifier,
            status="PENDING_VERIFICATION",
        )
        notifications.notify_submitted(incident)
        self.assertEqual(len(mail.outbox), 1)
        log = NotificationLog.objects.get(incident=incident)
        self.assertEqual(log.status, "SENT")

    def test_send_skips_recipient_without_email(self):
        self.verifier.email = ""
        self.verifier.save(update_fields=["email"])
        incident = make_incident(self.reporter, verifier=self.verifier)
        notifications.notify_submitted(incident)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationLog.objects.count(), 0)

    def test_notify_closed_sends_to_reporter_and_verifier(self):
        incident = make_incident(
            self.reporter,
            verifier=self.verifier,
            approver=self.approver,
            incident_id="0726001",
            status="CLOSED",
        )
        notifications.notify_closed(incident)
        self.assertEqual(len(mail.outbox), 2)

    def test_notify_reporter_returned(self):
        incident = make_incident(self.reporter, verifier=self.verifier, return_comment="Fix this.")
        notifications.notify_reporter_returned(incident)
        self.assertEqual(len(mail.outbox), 1)

    def test_notify_verifier_rejected_by_approver(self):
        incident = make_incident(self.reporter, verifier=self.verifier, approver=self.approver)
        notifications.notify_verifier_rejected_by_approver(incident)
        self.assertEqual(len(mail.outbox), 1)

    @patch("incidents.services.notifications.send_mail", side_effect=Exception("smtp down"))
    def test_send_logs_failure_without_raising(self, _send_mail_mock):
        incident = make_incident(self.reporter, verifier=self.verifier)
        notifications.notify_submitted(incident)
        log = NotificationLog.objects.get(incident=incident)
        self.assertEqual(log.status, "FAILED")

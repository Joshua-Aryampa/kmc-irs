from django.test import TestCase

from accounts.models import Role
from incidents.models import IncidentStatus
from incidents.permissions import (
    actionable_incidents_for_user,
    incidents_for_user,
    queue_counts,
    user_can_view_incident,
)
from incidents.tests.helpers import add_photo, make_incident, make_user


class PermissionTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter")
        self.verifier = make_user("verifier")
        self.approver = make_user("approver")
        self.ceo = make_user("ceo", role=Role.CEO)
        self.admin = make_user("admin", role=Role.ADMIN)
        self.other = make_user("other")

    def test_draft_visible_only_to_reporter(self):
        draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        self.assertTrue(user_can_view_incident(self.reporter, draft))
        self.assertFalse(user_can_view_incident(self.ceo, draft))
        self.assertFalse(user_can_view_incident(self.other, draft))

    def test_submitted_incident_visible_to_participants(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self.assertTrue(user_can_view_incident(self.verifier, incident))
        self.assertFalse(user_can_view_incident(self.other, incident))

    def test_ceo_sees_non_draft_incidents(self):
        incident = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        self.assertTrue(user_can_view_incident(self.ceo, incident))

    def test_incidents_for_user_excludes_other_drafts(self):
        own_draft = make_incident(self.reporter, status=IncidentStatus.DRAFT)
        other_draft = make_incident(self.other, status=IncidentStatus.DRAFT)
        submitted = make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        visible = set(incidents_for_user(self.reporter).values_list("pk", flat=True))
        self.assertIn(own_draft.pk, visible)
        self.assertIn(submitted.pk, visible)
        self.assertNotIn(other_draft.pk, visible)

    def test_queue_counts_for_assigned_user(self):
        make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=self.verifier,
        )
        make_incident(
            self.reporter,
            status=IncidentStatus.PENDING_APPROVAL,
            verifier=self.verifier,
            approver=self.approver,
        )
        counts = queue_counts(self.verifier)
        self.assertEqual(counts["queue_verify"], 1)
        self.assertEqual(counts["queue_approve"], 0)

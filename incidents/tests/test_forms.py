from django.test import TestCase

from incidents.forms import CommentForm, IncidentForm, VerifierActionForm, witness_formset
from incidents.scene_locations import SCENE_LOCATION_OTHER
from incidents.tests.helpers import base_incident_fields, make_incident, make_user, witness_formset_management, witness_row


class FormTests(TestCase):
    def setUp(self):
        self.reporter = make_user("reporter", keycloak_id="kc-reporter")
        self.verifier = make_user("verifier", keycloak_id="kc-verifier")
        self.approver = make_user("approver", keycloak_id="kc-approver")

    def test_draft_form_allows_partial_data(self):
        form = IncidentForm({"description": "Partial draft"}, submitting=False, reporter=self.reporter)
        self.assertTrue(form.is_valid())

    def test_submit_form_requires_declaration_and_verifier(self):
        data = base_incident_fields()
        data.update(
            {
                "confirm": "",
                "verifier_keycloak_id": "",
                "verifier_name": "",
            }
        )
        form = IncidentForm(data, submitting=True, reporter=self.reporter)
        self.assertFalse(form.is_valid())

    def test_submit_form_valid_with_verifier(self):
        data = base_incident_fields()
        data.update(
            {
                "confirm": "on",
                "verifier_keycloak_id": self.verifier.keycloak_id,
                "verifier_name": self.verifier.full_name,
            }
        )
        form = IncidentForm(data, submitting=True, reporter=self.reporter)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["selected_verifier"], self.verifier)

    def test_submit_form_rejects_reporter_as_verifier(self):
        data = base_incident_fields()
        data.update(
            {
                "confirm": "on",
                "verifier_keycloak_id": self.reporter.keycloak_id,
                "verifier_name": self.reporter.full_name,
            }
        )
        form = IncidentForm(data, submitting=True, reporter=self.reporter)
        self.assertFalse(form.is_valid())

    def test_verifier_action_form_requires_approver(self):
        incident = make_incident(self.reporter, verifier=self.verifier)
        form = VerifierActionForm({"severity": "MINOR"}, incident=incident)
        self.assertFalse(form.is_valid())

    def test_verifier_action_form_valid(self):
        incident = make_incident(self.reporter, verifier=self.verifier)
        form = VerifierActionForm(
            {
                "severity": "MINOR",
                "approver_keycloak_id": self.approver.keycloak_id,
                "approver_name": self.approver.full_name,
            },
            incident=incident,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_comment_form_requires_minimum_length(self):
        form = CommentForm({"comment": "short"})
        self.assertFalse(form.is_valid())
        form = CommentForm({"comment": "This is a valid reject comment."})
        self.assertTrue(form.is_valid())

    def test_witness_formset_requires_one_witness_on_submit(self):
        incident = make_incident(self.reporter)
        data = {}
        data.update(witness_formset_management())
        data.update(witness_row(index=0, keycloak_id="", name=""))
        formset = witness_formset(instance=incident, data=data, submitting=True)
        self.assertFalse(formset.is_valid())

    def test_submit_form_requires_involves_and_classifications(self):
        data = base_incident_fields()
        data.update(
            {
                "involves_person": "",
                "classification_injury": "",
                "confirm": "on",
                "verifier_keycloak_id": self.verifier.keycloak_id,
                "verifier_name": self.verifier.full_name,
            }
        )
        form = IncidentForm(data, submitting=True, reporter=self.reporter)
        self.assertFalse(form.is_valid())

    def test_submit_form_other_location(self):
        data = base_incident_fields()
        data.update(
            {
                "location_choice": SCENE_LOCATION_OTHER,
                "scene_location_other": "Custom bay",
                "confirm": "on",
                "verifier_keycloak_id": self.verifier.keycloak_id,
                "verifier_name": self.verifier.full_name,
            }
        )
        form = IncidentForm(data, submitting=True, reporter=self.reporter)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["scene_location"], "Custom bay")

    def test_witness_formset_accepts_selected_witness(self):
        incident = make_incident(self.reporter)
        data = {}
        data.update(witness_formset_management())
        data.update(
            witness_row(
                index=0,
                keycloak_id=self.verifier.keycloak_id,
                name=self.verifier.full_name,
            )
        )
        formset = witness_formset(instance=incident, data=data, submitting=True)
        self.assertTrue(formset.is_valid(), formset.errors)

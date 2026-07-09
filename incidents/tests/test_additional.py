from unittest.mock import MagicMock, patch

from django import forms
from django.test import TestCase, override_settings

from incidents.forms import validate_photo_uploads
from incidents.services import keycloak, signatures
from incidents.tests.helpers import make_test_image, make_user


class AdditionalCoverageTests(TestCase):
    def test_validate_photo_uploads_rejects_invalid_type(self):
        bad = make_test_image("bad.txt")
        bad.content_type = "text/plain"
        with self.assertRaises(forms.ValidationError):
            validate_photo_uploads([bad], existing_count=0)

    def test_validate_photo_uploads_accepts_jpeg(self):
        good = make_test_image()
        result = validate_photo_uploads([good], existing_count=0)
        self.assertEqual(len(result), 1)

    @override_settings(KEYCLOAK_SERVER_URL="https://auth.example.com", KEYCLOAK_REALM="test")
    @patch("incidents.services.keycloak._admin_token", return_value="token")
    @patch("incidents.services.keycloak.requests.get")
    def test_resolve_user_creates_user_from_keycloak(self, get_mock, _token_mock):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "id": "new-kc-id",
            "username": "newhire",
            "email": "new@test.local",
            "firstName": "New",
            "lastName": "Hire",
            "enabled": True,
            "attributes": {"designation": ["Technician"]},
        }
        get_mock.return_value = response
        user = keycloak.resolve_user("new-kc-id")
        self.assertEqual(user.username, "newhire")
        self.assertEqual(user.designation, "Technician")

    @override_settings(
        SIGNATURE_BASE_URL="https://signatures.example.com/",
        SIGNATURE_PATH_TEMPLATE="{keycloak_id}.png",
    )
    @patch("incidents.services.signatures.get_signature_url", return_value="")
    @patch("incidents.services.signatures.requests.get")
    def test_fetch_signature_file_legacy_url(self, get_mock, _kc_mock):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Content-Type": "image/png"}
        response.content = b"png-bytes"
        get_mock.return_value = response
        user = make_user("legacy", keycloak_id="kc-legacy")
        image = signatures.fetch_signature_file(user)
        self.assertIsNotNone(image)

    @patch("incidents.services.signatures.fetch_signature_file")
    def test_attach_signature_saves_image(self, fetch_mock):
        from django.core.files.base import ContentFile
        from incidents.tests.helpers import make_incident

        fetch_mock.return_value = ContentFile(b"img", name="sig.png")
        reporter = make_user("reporter")
        incident = make_incident(reporter)
        signatures.attach_signature(incident, "reporter_signature", reporter)
        self.assertTrue(incident.reporter_signature)

    @patch("incidents.services.signatures.fetch_signature_file")
    def test_attach_signature_clears_field_when_missing(self, fetch_mock):
        from incidents.tests.helpers import make_incident

        fetch_mock.return_value = None
        reporter = make_user("reporter2")
        incident = make_incident(reporter)
        signatures.attach_signature(incident, "reporter_signature", reporter)
        self.assertFalse(incident.reporter_signature)

    @override_settings(KEYCLOAK_SERVER_URL="https://auth.example.com", KEYCLOAK_REALM="test")
    @patch("incidents.services.keycloak._admin_token", return_value="token")
    @patch("incidents.services.keycloak.requests.get")
    def test_search_employees_via_keycloak_api(self, get_mock, _token_mock):
        get_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "id": "api-user",
                    "firstName": "Api",
                    "lastName": "User",
                    "username": "apiuser",
                }
            ],
        )
        results = keycloak.search_employees("api")
        self.assertEqual(results[0]["name"], "Api User")

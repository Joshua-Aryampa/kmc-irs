from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from incidents.services import keycloak, signatures
from incidents.tests.helpers import make_user


class KeycloakServiceTests(TestCase):
    @override_settings(KEYCLOAK_SERVER_URL="")
    def test_search_employees_falls_back_to_local_users(self):
        make_user("alice")
        results = keycloak.search_employees("ali")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice User")

    def test_resolve_user_returns_existing_local_user(self):
        user = make_user("bob", keycloak_id="kc-bob")
        resolved = keycloak.resolve_user(user.keycloak_id)
        self.assertEqual(resolved.pk, user.pk)

    @override_settings(KEYCLOAK_SERVER_URL="https://auth.example.com", KEYCLOAK_REALM="test")
    @patch("incidents.services.keycloak._admin_token", return_value="token")
    @patch("incidents.services.keycloak.requests.get")
    def test_get_signature_url_reads_attribute(self, get_mock, _token_mock):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "attributes": {"signature": ["https://example.com/sig.jpg"]}
        }
        get_mock.return_value = response
        url = keycloak.get_signature_url("kc-123")
        self.assertEqual(url, "https://example.com/sig.jpg")

    @override_settings(KEYCLOAK_SERVER_URL="")
    def test_get_signature_url_empty_without_keycloak(self):
        self.assertEqual(keycloak.get_signature_url("kc-123"), "")


class SignatureServiceTests(TestCase):
    @patch("incidents.services.signatures.get_signature_url", return_value="https://example.com/sig.png")
    @patch("incidents.services.signatures.requests.get")
    def test_fetch_signature_file_from_keycloak_url(self, get_mock, _url_mock):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Content-Type": "image/png"}
        response.content = b"png-bytes"
        get_mock.return_value = response
        user = make_user("signer", keycloak_id="kc-signer")
        image = signatures.fetch_signature_file(user)
        self.assertIsNotNone(image)
        self.assertTrue(image.name.endswith(".png"))

    @patch("incidents.services.signatures.get_signature_url", return_value="")
    def test_fetch_signature_file_returns_none_when_missing(self, _url_mock):
        user = make_user("nosig", keycloak_id="kc-nosig")
        self.assertIsNone(signatures.fetch_signature_file(user))

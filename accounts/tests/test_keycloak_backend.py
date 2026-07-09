from accounts.keycloak_backend import KmcOIDCAuthenticationBackend
from accounts.models import Role, User
from django.test import TestCase


class KeycloakBackendTests(TestCase):
    def setUp(self):
        self.backend = KmcOIDCAuthenticationBackend()

    def test_map_role_admin(self):
        claims = {"realm_access": {"roles": ["irs-admin"]}}
        self.assertEqual(self.backend._map_role(claims), Role.ADMIN)

    def test_map_role_ceo(self):
        claims = {"resource_access": {"irs": {"roles": ["ceo"]}}}
        self.assertEqual(self.backend._map_role(claims), Role.CEO)

    def test_map_role_defaults_to_worker(self):
        self.assertEqual(self.backend._map_role({}), Role.WORKER)

    def test_filter_users_by_claims_uses_sub(self):
        user = User.objects.create_user(
            username="kcuser",
            password="testpass123",
            keycloak_id="sub-123",
        )
        qs = self.backend.filter_users_by_claims({"sub": "sub-123"})
        self.assertEqual(qs.get(), user)

    def test_sync_user_updates_profile_fields(self):
        user = User.objects.create_user(username="syncme", password="testpass123")
        claims = {
            "sub": "sub-999",
            "email": "sync@test.local",
            "given_name": "Sync",
            "family_name": "User",
            "preferred_username": "syncuser",
            "designation": "Engineer",
            "realm_access": {"roles": ["ceo"]},
        }
        self.backend._sync_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.keycloak_id, "sub-999")
        self.assertEqual(user.role, Role.CEO)
        self.assertEqual(user.designation, "Engineer")

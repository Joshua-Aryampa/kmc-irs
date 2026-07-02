from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.core.exceptions import SuspiciousOperation

import jwt

from accounts.models import Role, User


class KmcOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def _verify_jws(self, payload, key):
        jws = jwt.get_unverified_header(payload)
        try:
            alg = jws["alg"]
        except KeyError as exc:
            raise SuspiciousOperation("No alg value found in header") from exc

        if alg != self.OIDC_RP_SIGN_ALGO:
            raise SuspiciousOperation(
                f"The provider algorithm {alg!r} does not match the client's OIDC_RP_SIGN_ALGO."
            )

        leeway = self.get_settings("OIDC_JWT_LEEWAY", 60)
        try:
            return jwt.decode(
                payload,
                key,
                algorithms=alg,
                options={"verify_aud": False},
                leeway=leeway,
            )
        except jwt.DecodeError as exc:
            raise SuspiciousOperation("JWS token verification failed.") from exc

    def create_user(self, claims):
        user = super().create_user(claims)
        self._sync_user(user, claims)
        return user

    def update_user(self, user, claims):
        self._sync_user(user, claims)
        return user

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if not sub:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(keycloak_id=sub)

    def _sync_user(self, user, claims):
        user.keycloak_id = claims.get("sub") or user.keycloak_id
        user.email = claims.get("email") or user.email
        user.first_name = claims.get("given_name") or user.first_name
        user.last_name = claims.get("family_name") or user.last_name
        user.username = claims.get("preferred_username") or user.username or user.keycloak_id
        user.designation = (
            claims.get("designation")
            or claims.get("title")
            or user.designation
            or ""
        )
        user.role = self._map_role(claims)
        user.is_active = True
        user.save()

    def _map_role(self, claims):
        roles = set(claims.get("realm_access", {}).get("roles", []))
        roles.update(claims.get("resource_access", {}).get("irs", {}).get("roles", []))
        normalized = {role.lower() for role in roles}
        if "irs-admin" in normalized or "admin" in normalized:
            return Role.ADMIN
        if "irs-ceo" in normalized or "ceo" in normalized:
            return Role.CEO
        return Role.WORKER

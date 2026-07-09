import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class KeycloakError(Exception):
    pass


def _admin_token():
    url = settings.KEYCLOAK_SERVER_URL.rstrip("/") + f"/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    response = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _display_name(user_payload):
    first = (user_payload.get("firstName") or "").strip()
    last = (user_payload.get("lastName") or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    return (user_payload.get("username") or user_payload.get("email") or "Unknown").strip()


def search_employees(name, limit=10):
    query = (name or "").strip()
    if len(query) < 2:
        return []

    if not settings.KEYCLOAK_SERVER_URL:
        return _search_local_users(query, limit)

    try:
        token = _admin_token()
    except Exception as exc:
        logger.warning("Keycloak admin token failed, falling back to local users: %s", exc)
        return _search_local_users(query, limit)

    url = urljoin(
        settings.KEYCLOAK_SERVER_URL.rstrip("/") + "/",
        f"admin/realms/{settings.KEYCLOAK_REALM}/users",
    )
    response = requests.get(
        url,
        params={"search": query, "max": limit},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()
    results = []
    for item in response.json()[:limit]:
        results.append(
            {
                "keycloak_id": item.get("id"),
                "name": _display_name(item),
            }
        )
    return results


def _search_local_users(query, limit):
    User = get_user_model()
    qs = User.objects.filter(is_active=True)
    matches = []
    needle = query.casefold()
    for user in qs:
        if needle in user.full_name.casefold() or needle in user.username.casefold():
            matches.append(
                {
                    "keycloak_id": user.keycloak_id or str(user.pk),
                    "name": user.full_name,
                    "designation": user.designation or "",
                    "user_id": user.pk,
                }
            )
        if len(matches) >= limit:
            break
    return matches


def get_signature_url(keycloak_id):
    keycloak_id = (keycloak_id or "").strip()
    if not keycloak_id or not settings.KEYCLOAK_SERVER_URL:
        return ""

    try:
        token = _admin_token()
    except Exception as exc:
        logger.warning("Keycloak admin token failed during signature lookup: %s", exc)
        return ""

    url = urljoin(
        settings.KEYCLOAK_SERVER_URL.rstrip("/") + "/",
        f"admin/realms/{settings.KEYCLOAK_REALM}/users/{keycloak_id}",
    )
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if response.status_code == 404:
            return ""
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Keycloak signature lookup failed for %s: %s", keycloak_id, exc)
        return ""

    attrs = response.json().get("attributes") or {}
    raw = attrs.get("signature")
    if not raw:
        return ""
    return (raw[0] if isinstance(raw, list) else str(raw)).strip()


def resolve_user(keycloak_id):
    if not keycloak_id:
        raise KeycloakError("Employee selection is required.")

    User = get_user_model()
    user = User.objects.filter(keycloak_id=keycloak_id).first()
    if user:
        return user

    if not settings.KEYCLOAK_SERVER_URL:
        user = User.objects.filter(pk=keycloak_id).first()
        if user:
            return user
        raise KeycloakError("Selected employee was not found.")

    try:
        token = _admin_token()
    except Exception as exc:
        raise KeycloakError("Unable to contact Keycloak to resolve employee.") from exc

    url = urljoin(
        settings.KEYCLOAK_SERVER_URL.rstrip("/") + "/",
        f"admin/realms/{settings.KEYCLOAK_REALM}/users/{keycloak_id}",
    )
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if response.status_code == 404:
        raise KeycloakError("Selected employee was not found in Keycloak.")
    response.raise_for_status()
    payload = response.json()
    user, _ = User.objects.update_or_create(
        keycloak_id=payload["id"],
        defaults={
            "username": payload.get("username") or payload["id"],
            "email": payload.get("email") or "",
            "first_name": payload.get("firstName") or "",
            "last_name": payload.get("lastName") or "",
            "designation": payload.get("attributes", {}).get("designation", [""])[0]
            if payload.get("attributes", {}).get("designation")
            else "",
            "is_active": payload.get("enabled", True),
        },
    )
    return user

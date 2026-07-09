import logging
from io import BytesIO
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image

from incidents.services.keycloak import get_signature_url

logger = logging.getLogger(__name__)


def _legacy_signature_urls(user):
    if not settings.SIGNATURE_BASE_URL or not user.keycloak_id:
        return []
    template = settings.SIGNATURE_PATH_TEMPLATE
    paths = [template.format(keycloak_id=user.keycloak_id, user_id=user.pk)]
    if ".png" in template.lower():
        paths.append(template.replace(".png", ".jpg").replace(".PNG", ".jpg").format(
            keycloak_id=user.keycloak_id, user_id=user.pk
        ))
    elif ".jpg" in template.lower() or ".jpeg" in template.lower():
        alt = template
        for ext in (".jpeg", ".jpg", ".JPEG", ".JPG"):
            alt = alt.replace(ext, ".png")
        paths.append(alt.format(keycloak_id=user.keycloak_id, user_id=user.pk))
    seen = set()
    urls = []
    for path in paths:
        url = urljoin(settings.SIGNATURE_BASE_URL.rstrip("/") + "/", path.lstrip("/"))
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _signature_urls(user):
    seen = set()
    urls = []

    if user.keycloak_id:
        keycloak_url = get_signature_url(user.keycloak_id)
        if keycloak_url:
            seen.add(keycloak_url)
            urls.append(keycloak_url)

    for url in _legacy_signature_urls(user):
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def fetch_signature_file(user):
    for url in _signature_urls(user):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                continue
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Signature fetch failed for %s at %s: %s", user.pk, url, exc)
            continue

        content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type not in {"image/png", "image/jpeg", "image/jpg"}:
            try:
                Image.open(BytesIO(response.content)).verify()
            except Exception:
                logger.warning("Unsupported signature format for user %s at %s", user.pk, url)
                continue

        ext = "png" if "png" in content_type else "jpg"
        return ContentFile(response.content, name=f"{user.keycloak_id or user.pk}.{ext}")
    return None


def attach_signature(incident, field_name, user):
    image_file = fetch_signature_file(user)
    field = getattr(incident, field_name)
    if image_file:
        if field:
            field.delete(save=False)
        field.save(image_file.name, image_file, save=False)
    elif field:
        field.delete(save=False)

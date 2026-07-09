"""Test settings: in-memory SQLite, no external services."""

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
KEYCLOAK_SERVER_URL = ""
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "login"
MEDIA_ROOT = BASE_DIR / "test_media"  # noqa: F405

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-change-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

if not DEBUG and SECRET_KEY == "dev-only-insecure-change-in-production":
    raise ImproperlyConfigured("Set a strong SECRET_KEY in production.")

_CONTEXT_PROCESSORS = [
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "incidents.context_processors.nav_counts",
    "incidents.context_processors.static_version",
]
if DEBUG:
    _CONTEXT_PROCESSORS.insert(0, "django.template.context_processors.debug")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mozilla_django_oidc",
    "accounts",
    "incidents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": _CONTEXT_PROCESSORS,
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_SQLITE = os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes")

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif DATABASE_URL.startswith("postgres"):
    from urllib.parse import unquote, urlparse

    parsed = urlparse(DATABASE_URL)
    if not parsed.path or parsed.path == "/":
        raise ValueError("Invalid DATABASE_URL: database name is required")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "localhost",
            "PORT": str(parsed.port or 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "").strip()
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "kmc").strip()
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "irs").strip()
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "").strip()
KEYCLOAK_ADMIN_CLIENT_ID = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", KEYCLOAK_CLIENT_ID).strip()
KEYCLOAK_ADMIN_CLIENT_SECRET = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", KEYCLOAK_CLIENT_SECRET).strip()

if KEYCLOAK_SERVER_URL:
    AUTHENTICATION_BACKENDS = [
        "accounts.keycloak_backend.KmcOIDCAuthenticationBackend",
    ]
    OIDC_RP_CLIENT_ID = KEYCLOAK_CLIENT_ID
    OIDC_RP_CLIENT_SECRET = KEYCLOAK_CLIENT_SECRET
    OIDC_OP_AUTHORIZATION_ENDPOINT = (
        f"{KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    )
    OIDC_OP_TOKEN_ENDPOINT = (
        f"{KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    )
    OIDC_OP_USER_ENDPOINT = (
        f"{KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
    )
    OIDC_OP_JWKS_ENDPOINT = (
        f"{KEYCLOAK_SERVER_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    )
    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_SCOPES = "openid email profile"
    OIDC_JWT_LEEWAY = int(os.getenv("OIDC_JWT_LEEWAY", "60"))
    OIDC_STORE_ACCESS_TOKEN = True
    OIDC_STORE_ID_TOKEN = True
    OIDC_CREATE_USER = True
    LOGIN_URL = "oidc_authentication_init"
    LOGOUT_REDIRECT_URL = "/"
else:
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "dashboard"
if not KEYCLOAK_SERVER_URL:
    LOGIN_URL = "login"
    LOGOUT_REDIRECT_URL = "login"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip().replace(" ", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "incidents@kiira.local").strip()
IRS_BASE_URL = os.getenv("IRS_BASE_URL", "http://127.0.0.1:8000")

SIGNATURE_BASE_URL = os.getenv("SIGNATURE_BASE_URL", "").strip()
SIGNATURE_PATH_TEMPLATE = os.getenv("SIGNATURE_PATH_TEMPLATE", "{keycloak_id}.png").strip()

INCIDENT_FORM_REFERENCE = os.getenv("INCIDENT_FORM_REFERENCE", "KMC.DQHSE.02/26-FM005").strip()
INCIDENT_LATE_MINUTES = 30
INCIDENT_MAX_PHOTOS = 10
INCIDENT_MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
INCIDENT_LIST_PAGE_SIZE = 20
DASHBOARD_RECENT_COUNT = 4

FILE_UPLOAD_MAX_MEMORY_SIZE = INCIDENT_MAX_PHOTO_BYTES * INCIDENT_MAX_PHOTOS

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ("1", "true", "yes")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").lower() in ("1", "true", "yes")
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"

"""
Django settings for the Vivalty SaaS platform.

Production-grade defaults:
- 12-factor configuration via environment variables (.env supported in dev)
- DRF + SimpleJWT authentication
- Postgres (with sqlite fallback for first boot only)
- Redis cache when REDIS_URL is provided, LocMem otherwise
- CORS for the Next.js frontend
- Service-layer architecture: views are thin, business logic lives in apps/*/services.py
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import os

from config.storage import configure_media_storage, use_s3_media

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", os.getenv("SECRET_KEY", "dev-insecure-change-me"))
DEBUG = env_bool("DJANGO_DEBUG", env_bool("DEBUG", True))
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    env_list("ALLOWED_HOSTS", ["*"] if DEBUG else []),
)

# Django 5 requires CSRF_TRUSTED_ORIGINS for HTTPS POSTs behind a proxy.
# Accepts full origins with scheme, e.g. "https://vivalty.com,https://www.vivalty.com".
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])

# Hard fail in production if the secret key was not rotated. This is cheaper than
# discovering predictable sessions in the wild.
if not DEBUG and SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a strong random value in production "
        "(it is currently the insecure default)."
    )
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS must be set (comma-separated) when DEBUG is off."
    )

# Railway's internal healthcheck hits the container with Host: healthcheck.railway.app.
# Without this, Django returns 400 DisallowedHost and the deploy is marked failed even
# though gunicorn is running. See https://docs.railway.com/guides/healthchecks
if not DEBUG:
    for _railway_host in (
        "healthcheck.railway.app",
        "localhost",
        "127.0.0.1",
        ".railway.app",
        ".railway.internal",
    ):
        if _railway_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_railway_host)
    _railway_private = os.getenv("RAILWAY_PRIVATE_DOMAIN", "").strip()
    if _railway_private and _railway_private not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_railway_private)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    # local
    "apps.users",
    "apps.geo",
    "apps.properties",
    "apps.ai_advisor",
    "apps.billing",
    "apps.web",
]

# Server-rendered website auth: send users back to /auth/login/ when they
# hit a protected page anonymously.
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "apps.web.middleware.CanonicalHostMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.seo",
                "apps.web.context_processors.company",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# Priority order:
#   1. DATABASE_URL  — set by Railway / Heroku / Render automatically
#   2. POSTGRES_HOST — individual vars (docker-compose, manual config)
#   3. SQLite        — local dev fallback (no DB server needed)
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    _u = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _u.path.lstrip("/"),
            "USER": _u.username,
            "PASSWORD": _u.password,
            "HOST": _u.hostname,
            "PORT": str(_u.port or 5432),
            "CONN_MAX_AGE": 60,
        }
    }
elif os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "vivalty"),
            "USER": os.getenv("POSTGRES_USER", "vivalty"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "vivalty"),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Cache ------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "vivalty-locmem",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Source static files (the built Tailwind CSS lives in backend/static/css/).
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# User uploads: local disk in dev, S3-compatible (Cloudflare R2 / AWS) in production.
# Static files: WhiteNoise in production (Django 5 uses STORAGES, not STATICFILES_STORAGE).
_media_storage = configure_media_storage()
_staticfiles_backend = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
STORAGES = {
    "default": _media_storage["default"],
    "staticfiles": {"BACKEND": _staticfiles_backend},
}
if _media_storage.get("media_url"):
    MEDIA_URL = _media_storage["media_url"]

if use_s3_media():
    # Exposed for django-storages and ops tooling.
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or None
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "auto")
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip() or None

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

# --- DRF --------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "ai_chat": "60/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS -------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", ["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True

# --- AI ---------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None

# --- Security ---------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Railway / Cloudflare / most modern PaaS terminate TLS at the edge and
    # already redirect HTTP to HTTPS at the proxy. Doing it again in Django
    # breaks the internal healthcheck (which uses plain HTTP). Default off;
    # set SECURE_SSL_REDIRECT=1 explicitly if your host does not redirect.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = False  # JS needs to read it for HTMX/fetch POSTs
    X_FRAME_OPTIONS = "DENY"

# --- Email (Resend) ---------------------------------------------------------
# In production set RESEND_API_KEY and DEFAULT_FROM_EMAIL. Locally we fall back
# to Django's console backend so dev signups still print the verify link.
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Vivalty <onboarding@resend.dev>")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")

# --- Company / legal (required for ad-platform landing-page policy) ----------
COMPANY_LEGAL_NAME = os.getenv("COMPANY_LEGAL_NAME", "Vivalty")
COMPANY_REGISTERED_ADDRESS = os.getenv(
    "COMPANY_REGISTERED_ADDRESS",
    "London, United Kingdom",
)
COMPANY_SUPPORT_EMAIL = os.getenv("COMPANY_SUPPORT_EMAIL", "hello@vivalty.com")
COMPANY_INVESTOR_EMAIL = os.getenv("COMPANY_INVESTOR_EMAIL", "investors@vivalty.com")
COMPANY_VAT_NUMBER = os.getenv("COMPANY_VAT_NUMBER", "")
if RESEND_API_KEY:
    EMAIL_BACKEND = "apps.web.services.emails.ResendEmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Bot protection (Cloudflare Turnstile) ---------------------------------
# Leave both blank in dev to disable the challenge.
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

# --- Auth tokens ------------------------------------------------------------
# Email verification links must be opened within this many hours.
EMAIL_VERIFY_TIMEOUT_HOURS = int(os.getenv("EMAIL_VERIFY_TIMEOUT_HOURS", "48"))
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2  # Django built-in: 2h reset link lifetime.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "vivalty": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

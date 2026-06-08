import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_LOCAL_SECRET_KEY = "django-insecure-copilot-cli-history-local-development"
INVALID_SECRET_KEYS = {"", "invalid", "invalid-secret", "changeme", "please-change-me"}


def validate_secret_key() -> str:
    secret_key = os.environ.get("DJANGO_SECRET_KEY")
    if secret_key is None:
        return DEFAULT_LOCAL_SECRET_KEY

    normalized_secret_key = secret_key.strip()
    if normalized_secret_key in INVALID_SECRET_KEYS:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a non-empty valid value.")

    return normalized_secret_key


SECRET_KEY = validate_secret_key()
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0",
).split(",")

INSTALLED_APPS: list[str] = ["health", "history_read_model"]
MIDDLEWARE: list[str] = []

ROOT_URLCONF = "backend_config.urls"
ASGI_APPLICATION = "backend_config.asgi.application"
WSGI_APPLICATION = "backend_config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

USE_TZ = True
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"

"""Minimal Django settings for the test suite."""

SECRET_KEY = "django-insecure-test-key"  # noqa: S105

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "taskiq_django",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

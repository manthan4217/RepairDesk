"""Production settings. Provide secrets through the process environment."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

# Production database engine guard: prevent accidental SQLite initialization
if DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":
    raise ImproperlyConfigured(
        f"Production deployment strictly requires MySQL ('django.db.backends.mysql'). "
        f"Configured backend '{DATABASES['default']['ENGINE']}' is not permitted in production."
    )

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Production transport and HSTS hardening (SEC-07)
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

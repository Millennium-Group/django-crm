"""Container/production settings.

Imports the project settings untouched and overrides only what a deployed
instance needs to be told from the outside: database, secret key, hosts,
serving of static files and TLS awareness.

Activate with ``DJANGO_SETTINGS_MODULE=webcrm.settings_docker`` (the image sets
it in the Dockerfile, and ``baremetal`` runs can pass it on the command line).

Everything is read from environment variables so the same image works for a
laptop compose file and a real deployment; see .env.example.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403


def _flag(name: str, default: str = '0') -> bool:
    return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes', 'on')


def _list(name: str, default: str = '') -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# ---- core --------------------------------------------------------------- #
DEBUG = _flag('DJANGO_DEBUG')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is required. Generate one with:\n'
        '  python -c "from django.core.management.utils import get_random_secret_key '
        'as k; print(k())"'
    )

ALLOWED_HOSTS = _list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

CSRF_TRUSTED_ORIGINS = _list('DJANGO_CSRF_TRUSTED_ORIGINS')


# ---- database ----------------------------------------------------------- #
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'crm'),
        'USER': os.environ.get('POSTGRES_USER', 'crm'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        'CONN_HEALTH_CHECKS': True,
    }
}


# ---- static files (whitenoise, no separate nginx needed) ----------------- #
MIDDLEWARE = list(MIDDLEWARE)
_security = 'django.middleware.security.SecurityMiddleware'
MIDDLEWARE.insert(MIDDLEWARE.index(_security) + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')

STATIC_ROOT = Path(os.environ.get('DJANGO_STATIC_ROOT', BASE_DIR / 'staticfiles'))
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # No manifest: hashed filenames break the CSV/XLSX download links and the
    # admin's inline favicons, which reference static paths at runtime.
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Caddy terminates TLS and forwards plain HTTP to gunicorn.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if _flag('DJANGO_HTTPS'):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ---- CRM specifics ------------------------------------------------------ #
# Randomised URL segments keep scanners off /admin and /login; override them
# per deployment so two installs do not share paths.
SECRET_CRM_PREFIX = os.environ.get('CRM_URL_PREFIX', SECRET_CRM_PREFIX)
SECRET_ADMIN_PREFIX = os.environ.get('CRM_ADMIN_PREFIX', SECRET_ADMIN_PREFIX)
SECRET_LOGIN_PREFIX = os.environ.get('CRM_LOGIN_PREFIX', SECRET_LOGIN_PREFIX)

CRM_IP = os.environ.get('CRM_IP', CRM_IP)
CRM_HOST = os.environ.get('CRM_HOST', CRM_HOST)

if os.environ.get('CRM_REPLY_TO'):
    CRM_REPLY_TO = [os.environ['CRM_REPLY_TO']]
if os.environ.get('NOT_ALLOWED_EMAILS'):
    NOT_ALLOWED_EMAILS = _list('NOT_ALLOWED_EMAILS')


# ---- outbound mail ------------------------------------------------------ #
EMAIL_HOST = os.environ.get('EMAIL_HOST', EMAIL_HOST)
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', EMAIL_PORT or 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', EMAIL_HOST_USER)
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', EMAIL_HOST_PASSWORD)
if os.environ.get('EMAIL_USE_TLS') is not None:
    EMAIL_USE_TLS = _flag('EMAIL_USE_TLS', '1')
if os.environ.get('DEFAULT_FROM_EMAIL'):
    DEFAULT_FROM_EMAIL = os.environ['DEFAULT_FROM_EMAIL']
    SERVER_EMAIL = DEFAULT_FROM_EMAIL


# ---- background threads ------------------------------------------------ #
# The reminder/notification senders start inside AppConfig.ready() and hit the
# database immediately. During schema creation on a fresh volume that races the
# migrations, so the entrypoint disables them for migrate/collectstatic.
DISABLE_DAEMON_THREADS = _flag('DJANGO_DISABLE_DAEMONS')


# ---- logging ------------------------------------------------------------ #
# Container logs are the interface; keep them on stdout.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

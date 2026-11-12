"""
Django settings for Starter Pilot.

Everything that differs between machines or hosting platforms comes from the
environment (a local .env file in development). .env.example lists every
variable and docs/DEVELOPER.md explains each one. Nothing here assumes a
particular hosting platform.
"""

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from csp.constants import NONE, SELF
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.modules import MODULE_APPS, MODULES_HOLD_PERSONAL_DATA
from config.platforms import platform_hostnames

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development variables from BASE_DIR/.env (DJANGO_ENV_FILE can point
# elsewhere; tests use it to start clean). Variables already set in the
# environment take precedence.
load_dotenv(os.environ.get('DJANGO_ENV_FILE') or BASE_DIR / '.env')

TRUE_VALUES = ('1', 'true', 'yes', 'on')


def env_str(name, default=''):
    return os.environ.get(name, default).strip()


def env_bool(name, default=False):
    value = os.environ.get(name, '').strip()
    return default if not value else value.lower() in TRUE_VALUES


def env_int(name, default):
    value = os.environ.get(name, '').strip()
    try:
        return int(value) if value else default
    except ValueError as exc:
        raise ImproperlyConfigured(f'{name} must be a whole number, got {value!r}.') from exc


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# Core settings

# Off unless DJANGO_DEBUG=true (set it only in your local .env).
DEBUG = env_bool('DJANGO_DEBUG')

SECRET_KEY = env_str('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY (see .env.example).')
    SECRET_KEY = 'django-insecure-local-development-only'  # noqa: S105 (DEBUG only, never production)

# Host names this site answers to, and https:// origins allowed to POST forms.
# Hosting platforms that publish the app's public host name in a variable
# (config/platforms.py) are added automatically; custom domains go here.
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
for _host in platform_hostnames(os.environ):
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
        CSRF_TRUSTED_ORIGINS.append(f'https://{_host}')


# Application definition

INSTALLED_APPS = [
    'core.admin_config.StaffAdminConfig',  # django.contrib.admin with the staff-only admin site
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'core.admin_config.TwoFactorConfig',  # django_otp.plugins.otp_totp
    'core.admin_config.SignInSecurityConfig',  # axes
    'core',
    *MODULE_APPS,
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.PermissionsPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'core.middleware.SessionLifetimeMiddleware',
    'core.middleware.StaffMFAMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    # Must stay last: it turns lockouts raised by authentication into responses.
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database: any PostgreSQL (Supabase, Neon, Aiven, Render, local...).
# Configure DATABASE_URL (preferred) or the individual DB_* variables. Query
# parameters in the URL (sslmode, channel_binding, connect_timeout...) are passed
# to the driver unchanged. There is deliberately no SQLite fallback.

SECURE_SSLMODES = {'require', 'verify-ca', 'verify-full'}
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


def database_from_env():
    url = os.environ.get('DATABASE_URL', '').strip()
    if url:
        parts = urlsplit(url)
        if parts.scheme not in ('postgres', 'postgresql'):
            raise ImproperlyConfigured('DATABASE_URL must be a postgresql:// URL.')
        config = {
            'NAME': unquote(parts.path.lstrip('/')) or 'postgres',
            'USER': unquote(parts.username or ''),
            'PASSWORD': unquote(parts.password or ''),
            'HOST': parts.hostname or '',
            'PORT': str(parts.port or 5432),
        }
        options = dict(parse_qsl(parts.query))
    else:
        missing = [name for name in ('DB_HOST', 'DB_USER', 'DB_PASSWORD') if not os.environ.get(name)]
        if missing:
            raise ImproperlyConfigured(
                'Database is not configured. Set DATABASE_URL or ' + ', '.join(missing) + ' (see .env.example).'
            )
        config = {
            'NAME': os.environ.get('DB_NAME', 'postgres'),
            'USER': os.environ['DB_USER'],
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': os.environ['DB_HOST'],
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
        options = {}

    if not (config['HOST'] and config['USER'] and config['PASSWORD']):
        raise ImproperlyConfigured('DATABASE_URL must include user, password, and host.')
    if config['HOST'].endswith('.pooler.supabase.com') and config['PORT'] == '6543':
        raise ImproperlyConfigured(
            "Supabase's transaction pooler (port 6543) is not supported; use the Session pooler URI (port 5432)."
        )

    # Hosted databases require encrypted connections; weaker modes are
    # accepted only for a PostgreSQL server on this machine.
    sslmode = os.environ.get('DB_SSLMODE') or options.get('sslmode') or 'require'
    if sslmode not in SECURE_SSLMODES and config['HOST'] not in LOCAL_HOSTS:
        raise ImproperlyConfigured(f'DB_SSLMODE must be one of {sorted(SECURE_SSLMODES)}, got {sslmode!r}.')
    options['sslmode'] = sslmode
    if os.environ.get('DB_SSLROOTCERT'):
        options['sslrootcert'] = os.environ['DB_SSLROOTCERT']

    return {
        'ENGINE': 'django.db.backends.postgresql',
        **config,
        'CONN_MAX_AGE': env_int('DB_CONN_MAX_AGE', 60),
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': options,
    }


DATABASES = {'default': database_from_env()}

# Drops the temporary test database even when a pooler keeps a connection to it.
TEST_RUNNER = 'config.test_runner.PoolerSafeTestRunner'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


# Site identity (shown on every page through core.context_processors.site)

SITE_NAME = env_str('SITE_NAME', 'Starter Pilot')
SITE_TAGLINE = env_str('SITE_TAGLINE', 'A throwaway project that tests the django-starter skill')
# Public base URL, used for links in emails (no trailing slash).
SITE_URL = env_str('SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
SITE_EMAIL = env_str('SITE_EMAIL', 'hello@example.com')
SITE_PHONE = env_str('SITE_PHONE')
SITE_ADDRESS = env_str('SITE_ADDRESS')
SITE_HOURS = env_str('SITE_HOURS')


# Authentication: Django accounts for staff, no public sign-up.

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'admin:index'
LOGOUT_REDIRECT_URL = 'login'
# Path of the staff administration (changing it hides it from casual scanning).
ADMIN_URL = env_str('DJANGO_ADMIN_URL', 'admin/').strip('/') + '/'

AUTHENTICATION_BACKENDS = [
    # django-axes first, so locked-out attempts never reach the password check.
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Argon2id for new and updated passwords; the others verify older hashes.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': env_int('PASSWORD_MIN_LENGTH', 12)},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Login lockout (django-axes): after LOGIN_FAILURE_LIMIT wrong passwords for the
# same username from the same address, further attempts are refused for
# LOGIN_LOCKOUT_MINUTES.
AXES_FAILURE_LIMIT = env_int('LOGIN_FAILURE_LIMIT', 5)
AXES_COOLOFF_TIME = timedelta(minutes=env_int('LOGIN_LOCKOUT_MINUTES', 15))
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'registration/locked_out.html'
AXES_CLIENT_IP_CALLABLE = 'core.net.client_ip'
AXES_VERBOSE = False

# Number of reverse proxies in front of the app that append to X-Forwarded-For.
# 0 trusts only the direct connection; set it to match your hosting (see
# docs/DEVELOPER.md), or client addresses can be spoofed.
TRUSTED_PROXY_COUNT = env_int('DJANGO_TRUSTED_PROXY_COUNT', 0)

# Two-factor login (TOTP authenticator app) for staff. On by default when a
# module stores customers' personal data.
STAFF_MFA_REQUIRED = env_bool('STAFF_MFA_REQUIRED', MODULES_HOLD_PERSONAL_DATA)
OTP_TOTP_ISSUER = SITE_NAME


# Sessions

# Idle timeout: the session expires after this long without a request.
SESSION_COOKIE_AGE = env_int('SESSION_IDLE_TIMEOUT_MINUTES', 30) * 60
SESSION_SAVE_EVERY_REQUEST = True
# Absolute timeout: signed-in sessions end this long after login regardless of
# activity (core.middleware.SessionLifetimeMiddleware).
SESSION_ABSOLUTE_TIMEOUT_SECONDS = env_int('SESSION_ABSOLUTE_TIMEOUT_HOURS', 12) * 3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
if not DEBUG:
    # The __Host- prefix makes browsers reject these cookies unless they are
    # Secure, host-only, and path=/ (it requires HTTPS, hence not in DEBUG).
    SESSION_COOKIE_NAME = '__Host-sessionid'
    CSRF_COOKIE_NAME = '__Host-csrftoken'


# Transport and browser security

# Hosting platforms terminate TLS at a proxy and forward the original scheme in
# a header. Set DJANGO_SECURE_PROXY_SSL_HEADER=off when nothing sits in front.
_proxy_header = env_str('DJANGO_SECURE_PROXY_SSL_HEADER', 'HTTP_X_FORWARDED_PROTO,https')
if _proxy_header.lower() not in ('', 'off', 'none', 'false'):
    _name, _, _value = _proxy_header.partition(',')
    SECURE_PROXY_SSL_HEADER = (_name.strip(), _value.strip() or 'https')

SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', not DEBUG)
# Health checks may arrive over plain HTTP from the platform; answer directly.
SECURE_REDIRECT_EXEMPT = [r'^healthz$', r'^readyz$']
SECURE_HSTS_SECONDS = 0 if DEBUG else env_int('DJANGO_HSTS_SECONDS', 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_HSTS_INCLUDE_SUBDOMAINS', True)
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
PERMISSIONS_POLICY = (
    'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
)
# HSTS preload is a deliberate, hard-to-undo opt-in per domain, not a default.
SILENCED_SYSTEM_CHECKS = ['security.W021']

# Content Security Policy (django-csp): everything is served from this site;
# no inline scripts or styles, no third-party origins. Violations are reported
# to core.views.csp_report and logged.
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': [SELF],
        'script-src': [SELF],
        'style-src': [SELF],
        'img-src': [SELF, 'data:'],
        'font-src': [SELF],
        'connect-src': [SELF],
        'form-action': [SELF],
        'frame-ancestors': [NONE],
        'base-uri': [SELF],
        'object-src': [NONE],
        'report-uri': '/csp-report/',
    },
}
if not DEBUG:
    CONTENT_SECURITY_POLICY['DIRECTIVES']['upgrade-insecure-requests'] = True


# Email: printed to the console until EMAIL_HOST is set.

EMAIL_HOST = env_str('EMAIL_HOST')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST else 'django.core.mail.backends.console.EmailBackend'
EMAIL_PORT = env_int('EMAIL_PORT', 587)
EMAIL_HOST_USER = env_str('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env_str('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env_str('DEFAULT_FROM_EMAIL', f'{SITE_NAME} <no-reply@example.com>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL


# Logging: everything to stdout, where hosting platforms collect it. Security
# events (sign-in, lockout, two-factor, CSP violations, spam) use the
# "security" logger and never include passwords or tokens.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        # UTC timestamps with an explicit Z, so events correlate across systems.
        'plain': {'()': 'core.logformat.UTCFormatter', 'format': '%(asctime)s %(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': env_str('LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'security': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'axes': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}


# Internationalization: one language per site, chosen in the project brief.

LANGUAGE_CODE = env_str('DJANGO_LANGUAGE_CODE', 'en')
TIME_ZONE = env_str('DJANGO_TIME_ZONE', 'America/Chicago')
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']


# Static files: served by WhiteNoise in production. Compression without a
# manifest, so templates render in tests without running collectstatic first.

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Owner-provided originals (committed) and the web-sized copies made from them
# by `manage.py optimize_images`.
IMAGES_SOURCE_DIR = BASE_DIR / 'src' / 'images'
IMAGES_OUTPUT_DIR = BASE_DIR / 'static' / 'img'


# Business modules (settings added by each module; see config/modules.py)

# CRM module: recipients of the email sent for each website message.
CRM_NOTIFY_EMAILS = env_list('CRM_NOTIFY_EMAILS', SITE_EMAIL)
# Website messages accepted per visitor address per hour.
CRM_CONTACT_RATE_LIMIT = env_int('CRM_CONTACT_RATE_LIMIT', 5)

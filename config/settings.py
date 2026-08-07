import os
import dj_database_url
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', cast=bool, default=True)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.railway.app').split(',')

# Default is 1000 -- too low for a bulk Order/ManualInvoice/BuyOrder admin
# form with a lot of line items (each readonly inline row still needs a
# hidden id field to save). Admin is staff-only/local-only, so raising
# this isn't a public-facing risk.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'django_filters',
    'products',
    'orders',
    'users',
    'payments',
    'inventory',
    'analytics_dashboard',
    'community',
]

# --- STATIC FILES (production) ---
# Django deliberately does NOT serve static files itself when DEBUG=False --
# that's correct, secure-by-default behavior, not a bug. WhiteNoise takes
# over that job in production: it serves static files directly from the
# WSGI app itself, no separate web server or CDN config needed.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # must sit right here -- after SecurityMiddleware, before everything else
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi.application'

_db_url = config('DATABASE_URL', default='')
if _db_url:
    DATABASES = {'default': dj_database_url.parse(_db_url, conn_max_age=600, conn_health_checks=True)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'pokemart',
            'USER': 'postgres',
            'PASSWORD': 'pokemart123',
            'HOST': '127.0.0.1',
            'PORT': '5432',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    # Consolidated 2026-07-30: this used to be defined twice further down
    # the file (a plain `REST_FRAMEWORK = {...}` reassignment, not a merge),
    # which silently discarded DEFAULT_SCHEMA_CLASS below and meant this
    # first block never actually took effect. Restored DEFAULT_SCHEMA_CLASS;
    # everything else here matches what was actually in effect (PAGE_SIZE 32,
    # the filter backends) so behaviour is unchanged.
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 32,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'PokeMart API',
    'DESCRIPTION': 'The ultimate Pokemon commerce API',
    'VERSION': '1.0.0',
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
AUTH_USER_MODEL = 'users.User'

POKEMONTCG_API_KEY = config('POKEMONTCG_API_KEY', default='')
PAYFAST_MERCHANT_ID = config('PAYFAST_MERCHANT_ID')
PAYFAST_MERCHANT_KEY = config('PAYFAST_MERCHANT_KEY')
PAYFAST_PASSPHRASE = config('PAYFAST_PASSPHRASE', default='')
PAYFAST_SANDBOX = config('PAYFAST_SANDBOX', cast=bool, default=True)

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r'^.*$'

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:3000,https://pokemart-api-production.up.railway.app,https://pokebulk.co.za,https://www.pokebulk.co.za,https://pos.pokebulk.co.za'
).split(',')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# JWT Authentication
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
}


# --- Standalone POS (pos.pokebulk.co.za) cross-subdomain cookie settings ---
CSRF_COOKIE_DOMAIN = ".pokebulk.co.za"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SITE_URL = config('SITE_URL', default='https://pokebulk.co.za')
API_URL = config('API_URL', default='https://pokemart-api-production.up.railway.app')

# --- Email ---
# CHANGED 2026-07-27: switched from raw SMTP to MailerSend's HTTPS API.
# Root cause found and confirmed: Railway blocks outbound SMTP connections
# at the platform/network level, regardless of destination -- both
# smtp.gmail.com:587 and mail.pokebulk.co.za:465 timed out identically at
# the socket.connect() step. No SMTP host will ever work from this
# platform. HTTPS (port 443) is not blocked, so MailerSendBackend
# (config/mailersend_backend.py) sends over their HTTPS API instead.
#
# The old EMAIL_HOST/EMAIL_PORT/EMAIL_USE_SSL/EMAIL_USE_TLS/EMAIL_HOST_USER/
# EMAIL_HOST_PASSWORD variables and config/ipv4_email_backend.py are no
# longer used by this setting, but are left in Railway/the repo rather than
# deleted, in case of a future rollback or local-dev SMTP testing need.
EMAIL_BACKEND = 'config.mailersend_backend.MailerSendBackend'
MAILERSEND_API_KEY = config('MAILERSEND_API_KEY', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='PokeBulk SA <orders@pokebulk.co.za>')
EMAIL_TIMEOUT = 30

# --- LOGGING ---
# CRITICAL FIX (2026-07-27): Django's default logging config only wires up
# a console handler for Django's OWN internal loggers, and only when
# DEBUG=True. Custom loggers created via logging.getLogger(__name__) in
# app code (e.g. users/views.py's logger.warning/info/exception calls)
# were NEVER connected to any handler in production (DEBUG=False) -- they
# executed but had nowhere to go, so nothing ever reached Railway's log
# stream. This explicit config attaches a StreamHandler (stdout) to the
# root logger, which Railway captures automatically. Without this, ANY
# logger.warning/info/error/exception call anywhere in the project is
# silently swallowed in production, not just the password reset ones.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env automatically for local development and simple deployments.
# Environment variables already set by the OS/hosting platform still take precedence.
load_dotenv(BASE_DIR / '.env')

# Detect the Django test runner so throttle rates (tuned for real traffic
# patterns) don't cause unrelated test failures when many requests fire in
# quick succession against the same in-memory cache.
TESTING = 'test' in sys.argv or 'PYTEST_CURRENT_TEST' in os.environ


def env_bool(name, default=False):
    return str(os.environ.get(name, str(default))).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


DEBUG = env_bool('DJANGO_DEBUG', False)

# A deployment without a secret key must fail at startup. A predictable fallback
# would let an accidentally misconfigured production instance sign forgeable
# sessions and JWTs.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set.')

# Development should be forgiving because the frontend may be opened through
# localhost, 127.0.0.1, a LAN IP, a VM IP, or a tunneled URL during testing.
# Production remains strict and must be configured with env vars.
if DEBUG:
    ALLOWED_HOSTS = ['*']
    CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
else:
    ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS') or ['localhost', '127.0.0.1']
    CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'storages',
    'portal',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'exam_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'exam_portal.wsgi.application'

# Database configuration: PostgreSQL with SQLite fallback
# BUGFIX: `os.environ.get('PGDATABASE' or 'DB_NAME')` always evaluated to
# 'PGDATABASE', so the DB_* fallbacks never worked. Fixed below.
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_NAME = os.environ.get('PGDATABASE') or os.environ.get('DB_NAME')
DB_USER = os.environ.get('PGUSER') or os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('PGPASSWORD') or os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('PGHOST') or os.environ.get('DB_HOST')
DB_PORT = os.environ.get('PGPORT') or os.environ.get('DB_PORT') or '5432'

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=int(os.environ.get('DJANGO_DB_CONN_MAX_AGE', '600')),
            conn_health_checks=True,
        )
    }
elif DB_NAME and DB_USER:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD or '',
            'HOST': DB_HOST or 'localhost',
            'PORT': DB_PORT,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'portal.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'

# ------------------------------------------------------------------------------
# FILE STORAGE (BACKBLAZE B2 / CLOUDFLARE R2 OBJECT STORAGE OR LOCAL FALLBACK)
# ------------------------------------------------------------------------------
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME') or os.environ.get('B2_BUCKET_NAME')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID') or os.environ.get('B2_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY') or os.environ.get('B2_APPLICATION_KEY')
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID')

if R2_BUCKET_NAME and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY:
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = (
        os.environ.get('R2_ENDPOINT_URL')
        or os.environ.get('B2_ENDPOINT_URL')
        or (f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else "https://s3.eu-central-003.backblazeb2.com")
    )
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME') or 'eu-central-003'
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = None  # Bucket remains private
    AWS_QUERYSTRING_AUTH = True  # Generate signed presigned URLs for secure access
    AWS_QUERYSTRING_EXPIRE = int(os.environ.get('R2_URL_EXPIRY', '3600'))  # 1 hour expiry
    AWS_S3_FILE_OVERWRITE = False
    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{R2_BUCKET_NAME}/"
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    MEDIA_URL = '/media/'

DEFAULT_FILE_STORAGE = STORAGES['default']['BACKEND']
STATICFILES_STORAGE = STORAGES['staticfiles']['BACKEND']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Max upload size for note attachments: 20 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
# In DEBUG, allow all origins so local/LAN frontend URLs do not break login.
# In production, configure CORS_ALLOWED_ORIGINS explicitly.
CORS_ALLOW_ALL_ORIGINS = bool(DEBUG)
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Disposition']

# The React app's public URL. Backend and frontend are deployed as separate
# services (e.g. Render + Vercel), so links generated by the backend — like
# password reset emails — must point here, never at request.get_host()
# (which is the API's own domain and doesn't serve any frontend routes).
# Falls back to the first configured CORS origin, then localhost for local dev.
FRONTEND_URL = (
    os.environ.get('FRONTEND_URL')
    or (CORS_ALLOWED_ORIGINS[0] if CORS_ALLOWED_ORIGINS else 'http://localhost:5173')
).rstrip('/')

# Safer production defaults. Enable HTTPS flags through env when deployed behind TLS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', False)
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ) if not TESTING else (),
    'DEFAULT_THROTTLE_RATES': {
        # Broad safeguards for public and authenticated API traffic. Sensitive
        # endpoints below use tighter scoped limits.
        'anon': '200/hour',
        'user': '2000/hour',
        'login': '20/hour',
        'code_run': '30/minute',
        'password_reset': '5/hour',
    } if not TESTING else {
        'anon': '100000/hour',
        'user': '100000/hour',
        'login': '100000/hour',
        'code_run': '100000/hour',
        'password_reset': '100000/hour',
    },
}

# Email is intentionally environment-driven. The console backend makes local
# development observable without pretending messages were delivered.
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'no-reply@examportal.local')
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('DJANGO_EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('DJANGO_EMAIL_USE_TLS', True)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'UPDATE_LAST_LOGIN': True,
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ------------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ------------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose' if not DEBUG else 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'portal': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}




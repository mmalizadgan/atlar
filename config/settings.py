"""
Django settings for the ATLAR project (فروشگاه پارچه مبلی آتلار).
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------
# Core / security
# -----------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-.env')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# -----------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',

    'widget_tweaks',

    'accounts',
    'core',
    'products',
    'cart',
    'orders',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'cart.middleware.CartMiddleware',
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
                'core.context_processors.site_settings',
                'cart.context_processors.cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# -----------------------------------------------------------------------
# Database — PostgreSQL (required)
# -----------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='atlar_db'),
        'USER': config('DB_USER', default='atlar_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    }
}

# -----------------------------------------------------------------------
# Auth — custom phone-based user + OTP login
# -----------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',   # phone + password, used by the admin panel
    'accounts.backends.OTPBackend',                 # phone + OTP, used by the storefront
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# -----------------------------------------------------------------------
# Internationalization — Persian / RTL
# -----------------------------------------------------------------------
LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']

# -----------------------------------------------------------------------
# Static & media files
# -----------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # Compressed (gzip/brotli) static files served directly by the app via WhiteNoise —
    # no separate CDN needed to get far-future cache headers + compression in production.
    # Once the design is stable, switch to whitenoise.storage.CompressedManifestStaticFilesStorage
    # for cache-busted filenames (safe to do once every {% static %} reference is finalized).
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------------------
# Caching — swap BACKEND to django_redis.cache.RedisCache + LOCATION for production
# -----------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'atlar-cache',
    }
}
CACHE_MIDDLEWARE_SECONDS = 60 * 10  # used for fragment-cached product listings

# -----------------------------------------------------------------------
# Sessions — anonymous cart lives in the session
# -----------------------------------------------------------------------
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days

# -----------------------------------------------------------------------
# OTP login settings
# -----------------------------------------------------------------------
OTP_CODE_LENGTH = config('OTP_CODE_LENGTH', default=5, cast=int)
OTP_EXPIRY_SECONDS = config('OTP_EXPIRY_SECONDS', default=120, cast=int)
OTP_RESEND_COOLDOWN_SECONDS = config('OTP_RESEND_COOLDOWN_SECONDS', default=90, cast=int)
OTP_MAX_ATTEMPTS = config('OTP_MAX_ATTEMPTS', default=5, cast=int)

# SMS provider — pluggable, see accounts/services/sms.py
# 'console' just logs/prints the code (safe default for local development).
SMS_PROVIDER = config('SMS_PROVIDER', default='console')
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_SENDER_LINE = config('SMS_SENDER_LINE', default='')

# -----------------------------------------------------------------------
# Bale Pay (بله‌پی) settings — filled in once the gateway is activated
# from the official @botfather bot inside Bale. See payments/gateways/bale_pay.py.
# -----------------------------------------------------------------------
BALE_PAY_MERCHANT_ID = config('BALE_PAY_MERCHANT_ID', default='')
BALE_PAY_API_KEY = config('BALE_PAY_API_KEY', default='')
BALE_PAY_CALLBACK_PATH = '/payments/bale/callback/'
SITE_BASE_URL = config('SITE_BASE_URL', default='http://127.0.0.1:8000')
SITE_NAME = 'آتلار'

# -----------------------------------------------------------------------
# Security hardening — active automatically once DEBUG=False
# -----------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

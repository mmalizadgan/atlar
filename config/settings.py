"""
Django settings for the ATLAR project (فروشگاه پارچه مبلی آتلار).

⚠️ این فایل بازنویسی شده است. تغییرات مهم:
  * SECRET_KEY پیش‌فرض ناامن حذف شد — در production بدون .env بالا نمی‌آید.
  * DEBUG پیش‌فرض False شد (قبلاً True بود و اگر .env فراموش شود سایت در حالت
    دیباگ بالا می‌آمد و stack trace + تنظیمات لو می‌رفت).
  * هدرهای امنیتی (CSP، Referrer-Policy، Permissions-Policy، ...) همیشه فعال شدند.
  * تنظیمات OTP سخت‌تر شد (۶ رقم، قفل و محدودیت نرخ بر پایه‌ی شماره و IP).
  * TRUST_PROXY_HEADERS برای تشخیص IP واقعی پشت پروکسی/CDN.
  * محدودیت حجم آپلود فایل.
  * تنظیمات LOGGING (بدون لاگ‌کردن کد OTP).
  * آدرس پنل ادمین از متغیر محیطی خوانده می‌شود.
"""
from pathlib import Path

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------
# Core / security
# -----------------------------------------------------------------------
# ⚠️ اصلاح: مقدار پیش‌فرض ناامن حذف شد. در production حتماً باید در .env باشد.
SECRET_KEY = config('SECRET_KEY', default='')

DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# آدرس مخفی پنل مدیریت (مثلاً ADMIN_URL=xk92-admin/ )
ADMIN_URL = config('ADMIN_URL', default='admin/')

if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            'SECRET_KEY تنظیم نشده است. یک کلید تصادفی بساز و در .env بگذار:\n'
            '  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )
    # در development یک کلید موقت (ولی تصادفی) می‌سازیم تا هر بار یکسان نباشد.
    import secrets as _secrets
    SECRET_KEY = _secrets.token_urlsafe(50)

if not DEBUG and '*' in ALLOWED_HOSTS:
    raise RuntimeError('ALLOWED_HOSTS در production نباید * باشد.')

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
    'config.middleware.SecurityHeadersMiddleware',   # ← جدید: CSP و هدرهای امنیتی
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
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
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
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# محدودیت حجم آپلود (ضد DoS با فایل ۱ گیگابایتی از پنل ادمین)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# -----------------------------------------------------------------------
# Caching
# ⚠️ مهم: محدودیت نرخ OTP فقط با کش «مشترک بین workerها» معنا دارد.
#   LocMemCache به‌ازای هر process جدا است → محدودیت‌ها به‌سادگی دور می‌شوند.
#   در production حتماً Redis بگذار (خط فعال‌شده را از کامنت خارج کن).
# -----------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'atlar-cache',
    },
    # 'default': {
    #     'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    #     'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
    # },
}
CACHE_MIDDLEWARE_SECONDS = 60 * 10

# -----------------------------------------------------------------------
# Sessions — anonymous cart lives in the session
# -----------------------------------------------------------------------
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14   # 14 days
SESSION_COOKIE_HTTPONLY = True           # ← جدید
SESSION_COOKIE_SAMESITE = 'Lax'          # ← جدید
CSRF_COOKIE_SAMESITE = 'Lax'             # ← جدید
CSRF_COOKIE_HTTPONLY = True              # ← جدید (توکن از JS خوانده نمی‌شود)
SESSION_COOKIE_NAME = 'atlar_sessionid'

# -----------------------------------------------------------------------
# OTP login settings — سخت‌سازی شده
# -----------------------------------------------------------------------
# ۵ رقم = ۱۰۰٫۰۰۰ حالت → در برابر حدس‌زدن ضعیف است. ۶ رقم حداقلِ قابل‌قبول،
# ۸ رقم برای سایت‌های پرمخاطب توصیه می‌شود.
OTP_CODE_LENGTH = config('OTP_CODE_LENGTH', default=6, cast=int)
OTP_EXPIRY_SECONDS = config('OTP_EXPIRY_SECONDS', default=180, cast=int)
OTP_RESEND_COOLDOWN_SECONDS = config('OTP_RESEND_COOLDOWN_SECONDS', default=120, cast=int)
OTP_MAX_ATTEMPTS = config('OTP_MAX_ATTEMPTS', default=5, cast=int)

# محدودیت‌های جدید (در accounts/services/otp.py استفاده می‌شوند)
OTP_MAX_PER_PHONE_PER_HOUR = config('OTP_MAX_PER_PHONE_PER_HOUR', default=3, cast=int)
OTP_MAX_PER_IP_PER_HOUR = config('OTP_MAX_PER_IP_PER_HOUR', default=10, cast=int)
OTP_MAX_VERIFY_PER_IP_PER_15MIN = config('OTP_MAX_VERIFY_PER_IP_PER_15MIN', default=15, cast=int)
OTP_MAX_FAILURES_PER_WINDOW = config('OTP_MAX_FAILURES_PER_WINDOW', default=8, cast=int)
OTP_FAILURE_WINDOW_MINUTES = config('OTP_FAILURE_WINDOW_MINUTES', default=15, cast=int)
OTP_LOCKOUT_MINUTES = config('OTP_LOCKOUT_MINUTES', default=15, cast=int)

# فقط وقتی True است هدر X-Forwarded-For برای تشخیص IP واقعی خوانده می‌شود.
# اگر پشت nginx/Cloudflare هستی True بگذار، وگرنه مهاجم می‌تواند IP جعل کند.
TRUST_PROXY_HEADERS = config('TRUST_PROXY_HEADERS', default=False, cast=bool)

# SMS provider — pluggable, see accounts/services/sms.py
SMS_PROVIDER = config('SMS_PROVIDER', default='console')
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_SENDER_LINE = config('SMS_SENDER_LINE', default='')

# -----------------------------------------------------------------------
# Bale Pay (بله‌پی) settings
# -----------------------------------------------------------------------
BALE_PAY_MERCHANT_ID = config('BALE_PAY_MERCHANT_ID', default='')
BALE_PAY_API_KEY = config('BALE_PAY_API_KEY', default='')
BALE_PAY_CALLBACK_PATH = '/payments/bale/callback/'
SITE_BASE_URL = config('SITE_BASE_URL', default='http://127.0.0.1:8000')
SITE_NAME = 'آتلار'

# -----------------------------------------------------------------------
# Logging — کد OTP هرگز لاگ نمی‌شود
# -----------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {'level': 'WARNING', 'propagate': True},
        'accounts.sms': {'level': 'INFO', 'propagate': True},
        'accounts.otp': {'level': 'INFO', 'propagate': True},
    },
}

# -----------------------------------------------------------------------
# Security hardening
# -----------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365          # یک سال (قبلاً ۳۰ روز بود)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید به فرم ۰۹xxxxxxxxx وارد شود.',
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        if not phone_number:
            raise ValueError('شماره موبایل الزامی است.')
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('ادمین باید is_staff=True داشته باشد.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('ادمین باید is_superuser=True داشته باشد.')
        return self._create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    کاربر با شماره موبایل به‌عنوان شناسه اصلی.
    مشتری‌ها با OTP وارد می‌شوند (رمز عبور استفاده نمی‌شود)،
    ادمین‌ها با شماره موبایل + رمز عبور وارد پنل مدیریت می‌شوند.
    """

    phone_number = models.CharField(
        max_length=11, unique=True, validators=[phone_validator], verbose_name='شماره موبایل'
    )
    first_name = models.CharField(max_length=60, blank=True, verbose_name='نام')
    last_name = models.CharField(max_length=60, blank=True, verbose_name='نام خانوادگی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_staff = models.BooleanField(default=False, verbose_name='دسترسی به پنل مدیریت')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ عضویت')

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        full_name = self.get_full_name()
        return f'{full_name} ({self.phone_number})' if full_name else self.phone_number

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.phone_number


# ---------------------------------------------------------------------------
# ⚠️ اصلاح امنیتی ۱ و ۲:
#   قبل: random.choices(...) → ژنراتور Mersenne Twister (قابل پیش‌بینی)
#   بعد:  secrets.choice → CSPRNG سیستم‌عامل ( crypto-grade )
# ---------------------------------------------------------------------------
def generate_otp_code():
    """کد یک‌بارمصرف فقط با RNG رمزنگارانه (secrets) ساخته می‌شود."""
    length = getattr(settings, 'OTP_CODE_LENGTH', 6)
    # ۶ رقمی = ۱۰۰٫۰۰۰ ترکیب؛ ۸ رقمی = ۱۰۰٫۰۰۰٫۰۰۰ ترکیب.
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def default_expiry():
    seconds = getattr(settings, 'OTP_EXPIRY_SECONDS', 180)
    return timezone.now() + timedelta(seconds=seconds)


class OTP(models.Model):
    """
    کد یک‌بارمصرف پیامکی برای ورود/ثبت‌نام با شماره موبایل.

    اصلاحات امنیتی این مدل:
      * کد هرگز به‌صورت متن خام ذخیره نمی‌شود؛ فقط HMAC-SHA256 آن (code_hash).
      * هر کد به session_key صادرکننده‌ی خودش گره خورده (session binding).
      * attempts شمارش می‌شود و کد بعد از OTP_MAX_ATTEMPTS «سوزانده» می‌شود.
    """

    phone_number = models.CharField(max_length=11, validators=[phone_validator], db_index=True)
    # جایگزین فیلد `code` — فقط هش کد ذخیره می‌شود.
    code_hash = models.CharField(max_length=64, editable=False)
    session_key = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'کد یکبار مصرف'
        verbose_name_plural = 'کدهای یکبار مصرف'
        indexes = [
            models.Index(fields=['phone_number', 'is_used', 'expires_at']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        # ⚠️ کد در هیچ reprای چاپ نمی‌شود (قبلاً `self.code` چاپ می‌شد).
        return f'{self.phone_number} - {self.created_at:%Y-%m-%d %H:%M}'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        return (
            not self.is_used
            and not self.is_expired
            and self.attempts < max_attempts
        )


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name='کاربر',
    )
    title = models.CharField('عنوان آدرس', max_length=80, blank=True, default='آدرس اصلی')
    recipient_name = models.CharField('نام گیرنده', max_length=120, blank=True, default='')
    phone_number = models.CharField('شماره تماس', max_length=11, validators=[phone_validator])
    province = models.CharField('استان', max_length=80, blank=True, default='')
    city = models.CharField('شهر', max_length=80)
    address_line = models.CharField('آدرس کامل', max_length=300)
    postal_code = models.CharField('کد پستی', max_length=10, blank=True, default='')
    plate = models.CharField('پلاک', max_length=20, blank=True, default='')
    unit = models.CharField('واحد', max_length=20, blank=True, default='')
    notes = models.CharField('توضیحات اضافی', max_length=300, blank=True, default='')
    is_default = models.BooleanField('پیش‌فرض', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'آدرس'
        verbose_name_plural = 'آدرس‌ها'
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(is_default=True),
                name='unique_default_address_per_user',
            )
        ]

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.phone_number} - {self.city}'

    def save(self, *args, **kwargs):
        force_insert = kwargs.pop('force_insert', False)
        force_update = kwargs.pop('force_update', False)
        using = kwargs.pop('using', None)

        with transaction.atomic(using=using):
            if self.is_default:
                Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
            elif not self.pk and not self.user.addresses.filter(is_default=True).exists():
                self.is_default = True

            super().save(*args, force_insert=force_insert, force_update=force_update, using=using, **kwargs)

            if self.is_default:
                Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)

    def delete(self, *args, **kwargs):
        was_default = self.is_default
        user = self.user
        super().delete(*args, **kwargs)
        if was_default:
            next_default = Address.objects.filter(user=user).order_by('-created_at').first()
            if next_default:
                next_default.is_default = True
                next_default.save(update_fields=['is_default'])

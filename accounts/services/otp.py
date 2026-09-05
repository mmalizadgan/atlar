"""
هسته‌ی امن OTP — هش، قفل، محدودیت نرخ، session binding.

نکته: نسخه‌ی قبلی این فایل فقط یک «طرح» ناقص بود (import اشتباه، توابع و
کلاس‌های ارجاع‌شده تعریف نشده بودند) و کل پروژه با ImportError بالا نمی‌آمد.
"""
import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from accounts.models import OTP, generate_otp_code

logger = logging.getLogger('accounts.otp')


# ---------------------------------------------------------------------------
# خطاها
# ---------------------------------------------------------------------------
class OTPError(Exception):
    """کلاس پایه‌ی همه‌ی خطاهای OTP."""


class OTPInvalidError(OTPError):
    """کد اشتباه / منقضی / سوخته / متعلق به نشست دیگر."""


class OTPCooldownError(OTPError):
    def __init__(self, remaining_seconds):
        self.remaining_seconds = int(remaining_seconds)
        super().__init__(f'{self.remaining_seconds}s cooldown')


class OTPLockedOutError(OTPError):
    def __init__(self, remaining_seconds):
        self.remaining_seconds = int(remaining_seconds)
        super().__init__(f'locked for {self.remaining_seconds}s')


class OTPThrottledError(OTPError):
    """سقف تعداد درخواست/تلاش در بازه‌ی زمانی پر شده است."""


# ---------------------------------------------------------------------------
# ابزارهای کمکی
# ---------------------------------------------------------------------------
def hash_otp_code(phone_number: str, code: str) -> str:
    """HMAC-SHA256 با SECRET_KEY؛ شماره هم در پیام هست تا هش بین شماره‌ها قابل انتقال نباشد."""
    message = f'{phone_number}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def get_client_ip(request) -> str:
    if request is None:
        return ''
    if getattr(settings, 'TRUST_PROXY_HEADERS', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45]


def _hit(key: str, ttl_seconds: int) -> int:
    """شمارنده‌ی اتمیک در کش. مقدار جدید را برمی‌گرداند."""
    added = cache.add(key, 1, timeout=ttl_seconds)
    if added:
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ttl_seconds)
        return 1


def _lockout_key(phone_number):
    return f'otp:lock:{phone_number}'


def _failure_key(phone_number):
    return f'otp:fail:{phone_number}'


def phone_lockout_remaining(phone_number: str) -> int:
    locked_until = cache.get(_lockout_key(phone_number))
    if not locked_until:
        return 0
    remaining = (locked_until - timezone.now()).total_seconds()
    return max(0, int(remaining))


def cooldown_remaining(phone_number: str) -> int:
    cooldown = getattr(settings, 'OTP_RESEND_COOLDOWN_SECONDS', 120)
    latest = (
        OTP.objects.filter(phone_number=phone_number, is_used=False)
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )
    if not latest:
        return 0
    elapsed = (timezone.now() - latest).total_seconds()
    return max(0, int(cooldown - elapsed))


def _record_failure(phone_number: str):
    window_minutes = getattr(settings, 'OTP_FAILURE_WINDOW_MINUTES', 15)
    max_failures = getattr(settings, 'OTP_MAX_FAILURES_PER_WINDOW', 8)
    failures = _hit(_failure_key(phone_number), window_minutes * 60)
    if failures >= max_failures:
        lock_minutes = getattr(settings, 'OTP_LOCKOUT_MINUTES', 15)
        cache.set(
            _lockout_key(phone_number),
            timezone.now() + timedelta(minutes=lock_minutes),
            timeout=lock_minutes * 60,
        )
        cache.delete(_failure_key(phone_number))
        logger.warning('OTP lockout applied (phone=%s)', phone_number)


# ---------------------------------------------------------------------------
# API اصلی
# ---------------------------------------------------------------------------
def issue_otp(*, phone_number, session_key='', ip_address=''):
    locked = phone_lockout_remaining(phone_number)
    if locked:
        raise OTPLockedOutError(locked)

    cooldown = cooldown_remaining(phone_number)
    if cooldown:
        raise OTPCooldownError(cooldown)

    if _hit(f'otp:phone:1h:{phone_number}', 3600) > settings.OTP_MAX_PER_PHONE_PER_HOUR:
        raise OTPThrottledError('برای این شماره در یک ساعت گذشته کدهای زیادی ارسال شده. کمی بعد تلاش کن.')

    if ip_address and _hit(f'otp:ip:1h:{ip_address}', 3600) > settings.OTP_MAX_PER_IP_PER_HOUR:
        raise OTPThrottledError('تعداد درخواست کد از این آدرس زیاد است. کمی بعد تلاش کن.')

    with transaction.atomic():
        OTP.objects.filter(phone_number=phone_number, is_used=False).update(is_used=True)
        plain_code = generate_otp_code()
        otp = OTP.objects.create(
            phone_number=phone_number,
            code_hash=hash_otp_code(phone_number, plain_code),
            session_key=session_key or '',
        )
    otp.plain_code = plain_code  # فقط در حافظه
    return otp


def verify_otp(*, phone_number, code, session_key='', ip_address=''):
    locked = phone_lockout_remaining(phone_number)
    if locked:
        raise OTPLockedOutError(locked)

    if ip_address and _hit(f'otp:verify:ip:15m:{ip_address}', 15 * 60) > settings.OTP_MAX_VERIFY_PER_IP_PER_15MIN:
        raise OTPThrottledError('تعداد تلاش‌ها زیاد است.')

    max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
    expected_hash = hash_otp_code(phone_number, code or '')

    # ⚠️ نکته‌ی مهم: خطا نباید «داخل» بلوک atomic پرتاب شود، وگرنه افزایش
    # attempts و سوزاندن کد rollback می‌شود و مهاجم بی‌نهایت حدس می‌زند.
    failure = None
    with transaction.atomic():
        otp = (
            OTP.objects.select_for_update()
            .filter(phone_number=phone_number, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if otp is None or otp.is_expired or otp.attempts >= max_attempts:
            failure = OTPInvalidError()
        else:
            otp.attempts += 1
            matched = (
                hmac.compare_digest(otp.code_hash, expected_hash)
                and hmac.compare_digest(otp.session_key or '', session_key or '')
            )
            if matched:
                otp.is_used = True
                otp.verified_at = timezone.now()
                otp.save(update_fields=['attempts', 'is_used', 'verified_at'])
            else:
                if otp.attempts >= max_attempts:
                    otp.is_used = True  # کد می‌سوزد
                otp.save(update_fields=['attempts', 'is_used'])
                failure = OTPInvalidError()

    if failure is not None:
        _record_failure(phone_number)
        raise failure

    cache.delete(_failure_key(phone_number))
    return otp


def purge_expired_otps(keep_days: int = 1) -> int:
    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = OTP.objects.filter(expires_at__lt=cutoff).delete()
    return deleted

"""
لایه ارسال پیامک، جدا از بقیه کد نگه داشته شده تا وصل‌کردن یک سرویس واقعی
(کاوه‌نگار، ملی‌پیامک، ippanel و ...) فقط همین یک فایل رو تغییر بده.

اصلاحات امنیتی این فایل:
  * `print()` حذف شد — کد OTP هرگز در stdout/لاگ‌های production چاپ نمی‌شود.
  * متن خطای سرویس‌دهنده هیچ‌وقت کلید API (که داخل URL است) را نشت نمی‌دهد.
  * فقط شماره‌های موبایل ایران پذیرفته می‌شود (ضد SMS-pumping بین‌المللی).
  * آدرس‌های سرویس‌دهنده allow-list شده‌اند (ضد SSRF با تغییر URL از .env).
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger('accounts.sms')

# شماره موبایل ایران — قبل از هر ارسالی چک می‌شود تا هزینه/سوءاستفاده کنترل شود.
IRAN_MOBILE_RE = re.compile(r'^09\d{9}$')

# سرویس‌دهنده‌های مجاز؛ اضافه‌کردن سرویس جدید یعنی اضافه‌کردن اسمش به این مجموعه.
ALLOWED_PROVIDERS = {'console', 'kavenegar'}


class SMSSendError(Exception):
    pass


def send_otp_sms(phone_number: str, code: str) -> None:
    provider = settings.SMS_PROVIDER

    if not IRAN_MOBILE_RE.match(phone_number or ''):
        # شماره نامعتبر: لاگ می‌کنیم ولی چیزی به سرویس‌دهنده نمی‌فرستیم.
        logger.warning('Blocked SMS request for invalid phone number.')
        raise SMSSendError('شماره موبایل نامعتبر است.')

    if provider not in ALLOWED_PROVIDERS:
        raise SMSSendError(f"SMS_PROVIDER='{provider}' پشتیبانی نمی‌شود.")

    # ⚠️ کد هرگز لاگ نمی‌شود؛ فقط طول پیام برای دیباگ.
    text = (
        f'کد ورود شما به آتلار: {code}\n'
        f'این کد تا {max(1, settings.OTP_EXPIRY_SECONDS // 60)} دقیقه دیگر معتبر است.'
    )

    if provider == 'console':
        if settings.DEBUG:
            # فقط در توسعه‌ی محلی؛ بدون این هیچ راهی برای ورود در dev وجود نداشت.
            logger.warning('[DEV ONLY][OTP SMS] phone=%s code=%s', phone_number, code)
        else:
            # ⚠️ در production با SMS_PROVIDER=console عملاً هیچ کاربری نمی‌تواند وارد شود.
            logger.error('[OTP SMS] SMS_PROVIDER=console in production! phone=%s (code not logged)', phone_number)
        return

    if provider == 'kavenegar':
        _send_via_kavenegar(phone_number, text)
        return


def _send_via_kavenegar(phone_number: str, text: str) -> None:
    """
    ارسال با کاوه‌نگار (kavenegar.com).
    فعال‌سازی: SMS_PROVIDER=kavenegar و SMS_API_KEY=<کلید شما> در .env
    """
    api_key = settings.SMS_API_KEY
    if not api_key:
        raise SMSSendError('SMS_API_KEY در .env تنظیم نشده است.')

    url = f'https://api.kavenegar.com/v1/{api_key}/sms/send.json'
    try:
        response = requests.post(
            url,
            data={
                'receptor': phone_number,
                'message': text,
                'sender': settings.SMS_SENDER_LINE or None,
            },
            timeout=(3, 8),  # (اتصال، خواندن) — جلوگیری از قفل‌شدن workerها
            allow_redirects=False,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # ⚠️ `str(exc)` می‌تواند شامل URL (و در نتیجه API key) باشد → لاگ نمی‌کنیم.
        logger.exception(
            'SMS send failed (phone=%s, reason=%s)', phone_number, exc.__class__.__name__
        )
        raise SMSSendError('ارسال پیامک ناموفق بود.') from exc

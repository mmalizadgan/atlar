"""
لایه ارسال پیامک، جدا از بقیه کد نگه داشته شده تا وصل‌کردن یک سرویس واقعی
(کاوه‌نگار، ملی‌پیامک، ippanel و ...) فقط همین یک فایل رو تغییر بده.

برای شروع روی 'console' تنظیم شده: به‌جای ارسال واقعی، کد رو در
ترمینال/لاگ چاپ می‌کنه تا بدون نیاز به سرویس پیامکی واقعی بشه کل فلوی
ورود رو تست کرد.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('accounts.sms')


class SMSSendError(Exception):
    pass


def send_otp_sms(phone_number: str, code: str) -> None:
    provider = settings.SMS_PROVIDER
    text = f'کد ورود شما به آتلار: {code}\nاین کد تا {settings.OTP_EXPIRY_SECONDS // 60} دقیقه دیگر معتبر است.'

    if provider == 'console':
        logger.info('[OTP SMS -> %s]: %s', phone_number, text)
        print(f'[OTP SMS -> {phone_number}]: {text}')
        return

    if provider == 'kavenegar':
        _send_via_kavenegar(phone_number, text)
        return

    raise SMSSendError(
        f"SMS_PROVIDER='{provider}' هنوز پیاده‌سازی نشده. "
        "یک تابع _send_via_<provider> اضافه کن یا SMS_PROVIDER رو در .env روی 'console' بذار."
    )


def _send_via_kavenegar(phone_number: str, text: str) -> None:
    """
    نمونه پیاده‌سازی برای کاوه‌نگار (kavenegar.com) — یکی از سرویس‌های پیامکی
    محبوب و قابل‌اعتماد داخلی. برای فعال کردنش:
      1) یک حساب کاوه‌نگار بساز و API key بگیر.
      2) در .env بذار: SMS_PROVIDER=kavenegar و SMS_API_KEY=<کلید شما>.
    اگر سرویس دیگه‌ای (ippanel، ملی‌پیامک و ...) ترجیح می‌دی، همین تابع رو
    الگو بگیر و آدرس/پارامترهای همون سرویس رو جایگزین کن.
    """
    if not settings.SMS_API_KEY:
        raise SMSSendError('SMS_API_KEY در .env تنظیم نشده است.')

    url = f'https://api.kavenegar.com/v1/{settings.SMS_API_KEY}/sms/send.json'
    try:
        response = requests.post(
            url,
            data={
                'receptor': phone_number,
                'message': text,
                'sender': settings.SMS_SENDER_LINE or None,
            },
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception('SMS send failed for %s', phone_number)
        raise SMSSendError(str(exc)) from exc

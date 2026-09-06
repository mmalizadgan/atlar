"""
لایه ارسال پیامک، جدا از بقیه کد نگه داشته شده تا وصل‌کردن یک سرویس واقعی
فقط همین یک فایل رو تغییر بده.

سرویس‌دهنده‌ی فعلی: **ملی‌پیامک** (melipayamak.com)
پیاده‌سازی بر اساس وب‌سرویس REST رسمی که در پکیج melipayamak-python استفاده شده:
    https://github.com/Melipayamak/melipayamak-python
    آدرس پایه: https://rest.payamak-panel.com/api/SendSMS/<Method>

دو روش ارسال پشتیبانی می‌شود:
  1) «خط خدماتی اشتراکی / پترن» (BaseServiceNumber) — پیشنهادی برای OTP.
     * سریع‌تر، بدون فیلتر شدن متن و به شماره‌هایی که پیامک تبلیغاتی‌شان بسته است هم می‌رسد.
     * باید در پنل ملی‌پیامک یک «متن پیش‌فرض» مثل «کد ورود شما به آتلار: {0}» بسازی و
       bodyId آن را در MELIPAYAMAK_BODY_ID بگذاری. فقط خودِ کد به‌عنوان آرگومان ارسال می‌شود.
  2) ارسال ساده (SendSMS) از خط اختصاصی خودت — اگر MELIPAYAMAK_BODY_ID خالی باشد.
     * SMS_SENDER_LINE باید شماره‌ی خط اختصاصی تو در ملی‌پیامک باشد.

اصلاحات امنیتی این فایل:
  * `print()` حذف شد — کد OTP هرگز در stdout/لاگ‌های production چاپ نمی‌شود.
    * نام‌کاربری/API Key در بدنه‌ی POST ارسال می‌شود (نه در URL) و هیچ‌وقت لاگ نمی‌شود.
  * فقط شماره‌های موبایل ایران پذیرفته می‌شود (ضد SMS-pumping بین‌المللی).
  * آدرس سرویس‌دهنده ثابت و allow-list شده است (ضد SSRF با تغییر URL از .env).
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger('accounts.sms')

# شماره موبایل ایران — قبل از هر ارسالی چک می‌شود تا هزینه/سوءاستفاده کنترل شود.
IRAN_MOBILE_RE = re.compile(r'^09\d{9}$')

# سرویس‌دهنده‌های مجاز؛ اضافه‌کردن سرویس جدید یعنی اضافه‌کردن اسمش به این مجموعه.
ALLOWED_PROVIDERS = {'console', 'melipayamak'}

# آدرس پایه‌ی REST ملی‌پیامک (همان چیزی که پکیج رسمی پایتون استفاده می‌کند).
MELIPAYAMAK_REST_BASE = 'https://rest.payamak-panel.com/api/SendSMS/'

# متدهای مجاز — از .env خوانده نمی‌شوند (ضد SSRF).
MELIPAYAMAK_ALLOWED_METHODS = {'SendSMS', 'BaseServiceNumber'}

# کدهای بازگشتی RetStatus / Value طبق مستندات ملی‌پیامک — فقط برای لاگ و عیب‌یابی.
MELIPAYAMAK_STATUS_MESSAGES = {
    0: 'نام کاربری یا رمز عبور اشتباه است.',
    1: 'درخواست با موفقیت انجام شد.',
    2: 'اعتبار کافی نیست.',
    3: 'محدودیت در ارسال روزانه.',
    4: 'محدودیت در حجم ارسال.',
    5: 'شماره فرستنده معتبر نیست.',
    6: 'سامانه در حال بروزرسانی است.',
    7: 'متن حاوی کلمه فیلتر شده است.',
    9: 'ارسال از خطوط عمومی از طریق وب‌سرویس امکان‌پذیر نیست.',
    10: 'کاربر مورد نظر فعال نیست.',
    11: 'ارسال نشده.',
    12: 'مدارک کاربر کامل نیست.',
    14: 'متن حاوی لینک است.',
    15: 'ارسال به بیش از یک شماره بدون درج «لغو۱۱» ممکن نیست.',
    16: 'شماره گیرنده یافت نشد.',
    17: 'متن پیامک خالی است.',
    19: 'از محدودیت ساعتی فراتر رفته‌اید.',
    35: 'شماره گیرنده در لیست سیاه مخابرات است.',
    # خطاهای مخصوص ارسال با پترن (BaseServiceNumber)
    -1: 'دسترسی استفاده از وب‌سرویس پترن غیرفعال است. با پشتیبانی ملی‌پیامک تماس بگیرید.',
    -2: 'محدودیت تعداد شماره؛ هر بار فقط یک شماره موبایل مجاز است.',
    -3: 'خط ارسالی در سیستم تعریف نشده است.',
    -4: 'کد متن (bodyId) صحیح نیست یا هنوز توسط مدیر سامانه تأیید نشده است.',
    -5: 'متن ارسالی با متغیرهای مشخص‌شده در پترن همخوانی ندارد.',
    -6: 'خطای داخلی ملی‌پیامک. با پشتیبانی تماس بگیرید.',
    -7: 'خطایی در شماره فرستنده رخ داده است.',
    -10: 'در میان متغیرهای ارسالی لینک وجود دارد.',
    -108: 'IP سرور به دلیل تلاش ناموفق استفاده از API مسدود شده است.',
    -109: 'الزام تنظیم IP مجاز برای استفاده از API در پنل ملی‌پیامک.',
    -110: 'الزام استفاده از ApiKey به جای رمز عبور در پنل ملی‌پیامک.',
}


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

    if provider == 'melipayamak':
        _send_via_melipayamak(phone_number, code=code, text=text)
        return


# ---------------------------------------------------------------------------
# ملی‌پیامک
# ---------------------------------------------------------------------------
def _melipayamak_credentials() -> dict:
    username = (getattr(settings, 'MELIPAYAMAK_USERNAME', '') or '').strip()
    # در REST ملی‌پیامک، API Key در همان فیلد `password` ارسال می‌شود.
    # نام قدیمی MELIPAYAMAK_PASSWORD برای سازگاری با .envهای قبلی پشتیبانی می‌شود.
    api_key = (
        getattr(settings, 'MELIPAYAMAK_API_KEY', '')
        or getattr(settings, 'MELIPAYAMAK_PASSWORD', '')
    )
    api_key = str(api_key).strip()
    if not username or not api_key:
        raise SMSSendError('MELIPAYAMAK_USERNAME / MELIPAYAMAK_API_KEY در .env تنظیم نشده است.')
    return {'username': username, 'password': api_key}


def _melipayamak_post(method: str, data: dict) -> dict:
    """
    یک درخواست POST به REST ملی‌پیامک می‌زند و JSON پاسخ را برمی‌گرداند.
    پاسخ استاندارد: {"Value": "...", "RetStatus": 1, "StrRetStatus": "Ok"}
    """
    if method not in MELIPAYAMAK_ALLOWED_METHODS:
        raise SMSSendError('متد ملی‌پیامک نامعتبر است.')

    url = f'{MELIPAYAMAK_REST_BASE}{method}'
    response = None
    try:
        response = requests.post(
            url,
            data={**data, **_melipayamak_credentials()},
            timeout=(3, 8),  # (اتصال، خواندن) — جلوگیری از قفل‌شدن workerها
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        # ⚠️ `str(exc)` می‌تواند شامل بدنه‌ی درخواست (و رمز پنل) باشد → فقط نوع خطا لاگ می‌شود.
        logger.error(
            'Melipayamak request failed (method=%s, reason=%s)', method, exc.__class__.__name__
        )
        raise SMSSendError('ارسال پیامک ناموفق بود.') from exc
    except ValueError as exc:  # JSON نامعتبر
        logger.error(
            'Melipayamak returned non-JSON response (method=%s, http=%s)',
            method, getattr(response, 'status_code', None),
        )
        raise SMSSendError('ارسال پیامک ناموفق بود.') from exc

    if not isinstance(payload, dict):
        logger.error('Melipayamak returned unexpected payload type (method=%s)', method)
        raise SMSSendError('ارسال پیامک ناموفق بود.')
    return payload


def _parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _check_melipayamak_result(method: str, phone_number: str, payload: dict) -> None:
    """
    موفقیت یعنی RetStatus == 1 و Value یک recId مثبت (عدد یکتای ارسال) باشد.
    هر چیز دیگری خطاست؛ کد خطا برای عیب‌یابی لاگ می‌شود (بدون اطلاعات حساس).
    """
    ret_status = _parse_int(payload.get('RetStatus'))
    value = _parse_int(payload.get('Value'))
    str_status = str(payload.get('StrRetStatus') or '')

    if ret_status == 1 and value is not None and value > 0:
        logger.info('Melipayamak SMS sent (method=%s, phone=%s, recId=%s)', method, phone_number, value)
        return

    # کد خطا یا در RetStatus است یا (در ارسال با پترن) داخل Value به صورت عدد منفی/کوچک.
    error_code = ret_status if ret_status not in (None, 1) else value
    reason = MELIPAYAMAK_STATUS_MESSAGES.get(error_code, str_status or 'خطای نامشخص')
    logger.error(
        'Melipayamak SMS rejected (method=%s, phone=%s, RetStatus=%s, Value=%s, reason=%s)',
        method, phone_number, ret_status, value, reason,
    )
    raise SMSSendError('ارسال پیامک ناموفق بود.')


def _send_via_melipayamak(phone_number: str, *, code: str, text: str) -> None:
    """
    ارسال با ملی‌پیامک (melipayamak.com).

    فعال‌سازی در .env:
        SMS_PROVIDER=melipayamak
        MELIPAYAMAK_USERNAME=<نام کاربری پنل>
        MELIPAYAMAK_API_KEY=<API Key پنل؛ در REST با نام password ارسال می‌شود>
        # برای سازگاری با تنظیمات قدیمی: MELIPAYAMAK_PASSWORD=<API Key>
        # روش ۱ (پیشنهادی برای OTP): خط خدماتی اشتراکی / پترن
        MELIPAYAMAK_BODY_ID=<کد متن پیش‌فرض تأییدشده در پنل>
        # روش ۲: ارسال ساده از خط اختصاصی (وقتی BODY_ID خالی است)
        SMS_SENDER_LINE=<شماره خط اختصاصی شما>
    """
    body_id = str(getattr(settings, 'MELIPAYAMAK_BODY_ID', '') or '').strip()

    if body_id:
        # معادل sms_rest.send_by_base_number(text, to, bodyId) در پکیج رسمی.
        # «text» اینجا فقط مقدار متغیرهای پترن است (چند متغیر با ; جدا می‌شوند)؛
        # برای OTP فقط خودِ کد ارسال می‌شود تا جای {0} در متن پیش‌فرض بنشیند.
        payload = _melipayamak_post(
            'BaseServiceNumber',
            {'to': phone_number, 'bodyId': body_id, 'text': code},
        )
        _check_melipayamak_result('BaseServiceNumber', phone_number, payload)
        return

    # معادل sms_rest.send(to, from, text, is_flash) در پکیج رسمی.
    sender = (getattr(settings, 'SMS_SENDER_LINE', '') or '').strip()
    if not sender:
        raise SMSSendError(
            'برای ارسال ساده با ملی‌پیامک باید SMS_SENDER_LINE (خط اختصاصی) تنظیم شود، '
            'یا MELIPAYAMAK_BODY_ID را برای ارسال با پترن مقدار بدهید.'
        )
    payload = _melipayamak_post(
        'SendSMS',
        {'to': phone_number, 'from': sender, 'text': text, 'isFlash': 'false'},
    )
    _check_melipayamak_result('SendSMS', phone_number, payload)

# accounts/services/otp.py (فایل جدید)
from config import settings


def issue_otp(*, phone_number, session_key='', ip_address=''):
    if phone_lockout_remaining(phone_number):
        raise OTPLockedOutError(...)

    cooldown = cooldown_remaining(phone_number)
    if cooldown:
        raise OTPCooldownError(cooldown)

    # سقف کد برای هر شماره در ساعت (ضد SMS-bombing)
    if _hit(f'otp:phone:1h:{phone_number}', 3600) > settings.OTP_MAX_PER_PHONE_PER_HOUR:
        raise OTPThrottledError(...)

    # سقف کد برای هر IP در ساعت (ضد ارسال گروهی به شماره‌های دیگر)
    if ip_address and _hit(f'otp:ip:1h:{ip_address}', 3600) > settings.OTP_MAX_PER_IP_PER_HOUR:
        raise OTPThrottledError(...)

    # فقط یک کد فعال؛ کدهای قبلی باطل می‌شوند
    OTP.objects.filter(phone_number=phone_number, is_used=False).update(is_used=True)
    plain_code = generate_otp_code()
    otp = OTP.objects.create(
        phone_number=phone_number,
        code_hash=hash_otp_code(phone_number, plain_code),
        session_key=session_key,
    )
    otp.plain_code = plain_code      # فقط در حافظه؛ در دیتابیس ذخیره نمی‌شود
    return otp


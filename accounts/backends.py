from django.contrib.auth import get_user_model

from .models import OTP

User = get_user_model()


class OTPBackend:
    """
    بک‌اند احراز هویت با شماره موبایل + کد یکبار مصرف (بدون رمز عبور).
    اگر کاربر با این شماره برای اولین‌بار وارد می‌شود، همین‌جا ساخته می‌شود
    (ثبت‌نام ضمنی هنگام اولین ورود).
    """

    def authenticate(self, request, phone_number=None, otp_code=None, **kwargs):
        if not phone_number or not otp_code:
            return None

        otp = (
            OTP.objects.filter(phone_number=phone_number, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if otp is None:
            return None

        if not otp.is_valid:
            return None

        if otp.code != otp_code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            return None

        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user, _ = User.objects.get_or_create(phone_number=phone_number)
        if not user.is_active:
            return None
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

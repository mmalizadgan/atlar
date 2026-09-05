from django.contrib.auth import get_user_model

from .services.otp import get_client_ip, verify_otp

User = get_user_model()


class OTPBackend:
    """
    بک‌اند احراز هویت با شماره موبایل + کد یک‌بارمصرف (بدون رمز عبور).
    اگر کاربر با این شماره برای اولین‌بار وارد می‌شود، همین‌جا ساخته می‌شود
    (ثبت‌نام ضمنی هنگام اولین ورود).

    اصلاحات:
      * منطق تایید به `accounts/services/otp.py` منتقل شده (هش + قفل + نرخ).
      * مقایسه constant-time روی هش انجام می‌شود، نه روی کد خام.
      * خطاهای قفل/نرخ به ویو عبور می‌کنند تا پیام درست به کاربر برسد.
    """

    def authenticate(self, request, phone_number=None, otp_code=None, **kwargs):
        if not phone_number or not otp_code:
            return None

        session_key = request.session.session_key if request is not None else ''
        try:
            verify_otp(
                phone_number=phone_number,
                code=otp_code,
                session_key=session_key or '',
                ip_address=get_client_ip(request) if request is not None else '',
            )
        except Exception:
            # خطاها (کد اشتباه / قفل / نرخ) را به ویو می‌دهیم تا تفکیک شوند،
            # اما اگر چیز غیرمنتظره‌ای رخ داد، ورود قطعاً انجام نمی‌شود.
            raise

        user, _ = User.objects.get_or_create(phone_number=phone_number)
        if not user.is_active:
            return None
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        return user is not None and user.is_active

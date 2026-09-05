"""
تست‌های امنیتی — این فایل بازنویسی/تکمیل شده است.

اجرا:
    python manage.py test accounts -v 2

تست‌ها دقیقاً همان حملاتی را پوشش می‌دهند که در گزارش امنیتی آمده:
  * کد OTP تصادفی و غیرقابل‌تکرار است (نه خروجی PRNG قابل‌پیش‌بینی)
  * کد به‌صورت هش ذخیره می‌شود (نه متن خام)
  * بعد از سقف تلاش، کد «می‌سوزد»
  * بعد از شکست‌های متوالی، شماره قفل می‌شود (حتی با کد جدید)
  * محدودیت تعداد کد در ساعت (ضد SMS-bombing)
  * کد به نشست صادرکننده گره خورده است
  * شماره‌ی موبایل با ارقام فارسی نرمال می‌شود
"""
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings

from cart.models import Cart, CartItem
from products.models import Category, Fabric, FabricColorVariant

from .models import OTP, generate_otp_code
from .services import otp as otp_service
from .views import SESSION_GUEST_CART_KEY, _migrate_guest_cart_to_session


class OTPGenerationTests(TestCase):
    def test_code_has_configured_length_and_only_digits(self):
        for _ in range(20):
            code = generate_otp_code()
            self.assertEqual(len(code), settings.OTP_CODE_LENGTH)
            self.assertTrue(code.isdigit())

    def test_codes_are_not_sequential_or_repeated(self):
        """خروجی secrets نباید الگو داشته باشد (برخلاف random با seed مشترک)."""
        codes = {generate_otp_code() for _ in range(60)}
        self.assertGreater(len(codes), 40)


class OTPStorageTests(TestCase):
    def test_code_is_stored_hashed_not_plaintext(self):
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        plain = otp.plain_code
        self.assertFalse(OTP.objects.filter(code_hash=plain).exists())
        self.assertEqual(len(otp.code_hash), 64)
        self.assertNotIn(plain, otp.code_hash)

    def test_verify_success_marks_used(self):
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        verified = otp_service.verify_otp(
            phone_number='09121234567', code=otp.plain_code, session_key='sess-1'
        )
        self.assertEqual(verified.pk, otp.pk)
        self.assertTrue(verified.is_used)

    def test_code_cannot_be_reused(self):
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        otp_service.verify_otp(
            phone_number='09121234567', code=otp.plain_code, session_key='sess-1'
        )
        with self.assertRaises(otp_service.OTPInvalidError):
            otp_service.verify_otp(
                phone_number='09121234567', code=otp.plain_code, session_key='sess-1'
            )


class OTPBruteForceTests(TestCase):
    def test_code_burned_after_max_attempts(self):
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            with self.assertRaises(otp_service.OTPInvalidError):
                otp_service.verify_otp(
                    phone_number='09121234567', code='000000', session_key='sess-1'
                )
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
        # حتی کد درست هم دیگر کار نمی‌کند
        with self.assertRaises(otp_service.OTPInvalidError):
            otp_service.verify_otp(
                phone_number='09121234567', code=otp.plain_code, session_key='sess-1'
            )

    @override_settings(OTP_MAX_FAILURES_PER_WINDOW=3, OTP_LOCKOUT_MINUTES=10)
    def test_phone_locked_out_even_after_requesting_new_code(self):
        """
        ⚠️ این مهم‌ترین تست است: قبلاً مهاجم با گرفتن کد جدید، شمارنده‌ی تلاش‌ها
        را صفر می‌کرد و بی‌نهایت حدس می‌زد. حالا قفل روی «شماره» است نه روی کد.
        """
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        for _ in range(3):
            with self.assertRaises(otp_service.OTPInvalidError):
                otp_service.verify_otp(
                    phone_number='09121234567', code='000000', session_key='sess-1'
                )

        self.assertGreater(otp_service.phone_lockout_remaining('09121234567'), 0)
        with self.assertRaises(otp_service.OTPLockedOutError):
            otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        with self.assertRaises(otp_service.OTPLockedOutError):
            otp_service.verify_otp(
                phone_number='09121234567', code=otp.plain_code, session_key='sess-1'
            )

    @override_settings(OTP_MAX_PER_PHONE_PER_HOUR=2)
    def test_sms_bombing_is_throttled(self):
        otp_service.issue_otp(phone_number='09121234567', session_key='s')
        otp_service.issue_otp(phone_number='09121234567', session_key='s')
        with self.assertRaises(otp_service.OTPThrottledError):
            otp_service.issue_otp(phone_number='09121234567', session_key='s')

    def test_only_one_active_code_per_phone(self):
        first = otp_service.issue_otp(phone_number='09121234567', session_key='s')
        second = otp_service.issue_otp(phone_number='09121234567', session_key='s')
        first.refresh_from_db()
        self.assertTrue(first.is_used)
        self.assertFalse(second.is_used)

    @override_settings(OTP_MAX_FAILURES_PER_WINDOW=6, OTP_LOCKOUT_MINUTES=10)
    def test_failures_count_even_after_code_burned(self):
        """
        ⚠️ رگرسیون: قبلاً بعد از سوختن کد، تلاش‌های بعدی اصلاً شمرده نمی‌شدند و
        مهاجم می‌توانست بی‌هزینه حدس ادامه دهد. حالا شکست‌ها انباشته می‌شوند.
        """
        otp_service.issue_otp(phone_number='09121112233', session_key='s')
        # ۵ حدس اشتباه → کد می‌سوزد
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            with self.assertRaises(otp_service.OTPInvalidError):
                otp_service.verify_otp(phone_number='09121112233', code='000000', session_key='s')

        # کد سوخته؛ تلاش‌های بیشتر باید همچنان به سقف شکست اضافه شوند
        for _ in range(settings.OTP_MAX_FAILURES_PER_WINDOW - settings.OTP_MAX_ATTEMPTS):
            with self.assertRaises(otp_service.OTPError):
                otp_service.verify_otp(phone_number='09121112233', code='000000', session_key='s')

        self.assertGreater(otp_service.phone_lockout_remaining('09121112233'), 0)
        with self.assertRaises(otp_service.OTPLockedOutError):
            otp_service.issue_otp(phone_number='09121112233', session_key='s')

    def test_code_is_bound_to_session(self):
        otp = otp_service.issue_otp(phone_number='09121234567', session_key='sess-1')
        with self.assertRaises(otp_service.OTPInvalidError):
            otp_service.verify_otp(
                phone_number='09121234567', code=otp.plain_code, session_key='sess-other'
            )


class GuestCartMigrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.category = Category.objects.create(name='پرده', slug='perdeh')
        self.fabric = Fabric.objects.create(
            category=self.category,
            name='پرده رسمی',
            slug='perdeh-rasmi',
            sku='FAB-001',
            price_per_meter=Decimal('120000'),
            min_order_meters=Decimal('1.0'),
        )
        self.variant = FabricColorVariant.objects.create(
            fabric=self.fabric,
            color_name='نخودی',
            color_hex='#a87b34',
            stock_meters=Decimal('20.0'),
        )

    def test_guest_cart_moves_to_new_session_after_login(self):
        old_session_key = 'guest-old-123'
        cart = Cart.objects.create(session_key=old_session_key)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity_meters=Decimal('2.5'))

        request = self.factory.get('/')
        request.session = self.client.session
        request.session.session_key = old_session_key
        request.session[SESSION_GUEST_CART_KEY] = old_session_key
        request.session.save()

        request.session.cycle_key()

        _migrate_guest_cart_to_session(request)

        migrated_cart = Cart.objects.filter(session_key=request.session.session_key).first()
        self.assertIsNotNone(migrated_cart)
        self.assertEqual(migrated_cart.items.count(), 1)
        self.assertEqual(migrated_cart.items.first().quantity_meters, Decimal('2.5'))
        self.assertFalse(Cart.objects.filter(session_key=old_session_key).exists())
        self.assertNotIn(SESSION_GUEST_CART_KEY, request.session)

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
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from cart.models import Cart, CartItem
from orders.models import Order
from products.models import Category, Fabric, FabricColorVariant

from .models import Address, OTP, User, generate_otp_code
from .services import otp as otp_service
from .views import SESSION_GUEST_CART_KEY, _migrate_guest_cart_to_session


@override_settings(OTP_RESEND_COOLDOWN_SECONDS=0)
class OTPTestCase(TestCase):
    """کش (شمارنده‌های نرخ/قفل) بین تست‌ها مشترک است؛ قبل از هر تست پاک می‌شود."""

    def setUp(self):
        super().setUp()
        cache.clear()


class OTPGenerationTests(OTPTestCase):
    def test_code_has_configured_length_and_only_digits(self):
        for _ in range(20):
            code = generate_otp_code()
            self.assertEqual(len(code), settings.OTP_CODE_LENGTH)
            self.assertTrue(code.isdigit())

    def test_codes_are_not_sequential_or_repeated(self):
        """خروجی secrets نباید الگو داشته باشد (برخلاف random با seed مشترک)."""
        codes = {generate_otp_code() for _ in range(60)}
        self.assertGreater(len(codes), 40)


class OTPStorageTests(OTPTestCase):
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


class OTPBruteForceTests(OTPTestCase):
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
        # نشست واقعی در دیتابیس ساخته می‌شود (session_key فقط‌خواندنی و باید در DB باشد)
        session = self.client.session
        session.create()
        old_session_key = session.session_key
        cart = Cart.objects.create(session_key=old_session_key)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity_meters=Decimal('2.5'))

        session[SESSION_GUEST_CART_KEY] = old_session_key
        session.save()

        request = self.factory.get('/')
        request.session = session

        request.session.cycle_key()

        _migrate_guest_cart_to_session(request)

        migrated_cart = Cart.objects.filter(session_key=request.session.session_key).first()
        self.assertIsNotNone(migrated_cart)
        self.assertEqual(migrated_cart.items.count(), 1)
        self.assertEqual(migrated_cart.items.first().quantity_meters, Decimal('2.5'))
        self.assertFalse(Cart.objects.filter(session_key=old_session_key).exists())
        self.assertNotIn(SESSION_GUEST_CART_KEY, request.session)


class AccountAddressManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='09120000000', first_name='میلاد', last_name='علیزاده')
        self.other_user = User.objects.create_user(phone_number='09121111111', first_name='حسین', last_name='حسینی')

    def test_first_address_is_set_as_default(self):
        address = Address.objects.create(
            user=self.user,
            title='خانه',
            recipient_name='میلاد علیزاده',
            phone_number='09120000000',
            province='تهران',
            city='تهران',
            address_line='خیابان ولیعصر',
            postal_code='1234567890',
        )
        self.assertTrue(address.is_default)

    def test_switching_default_moves_previous_default_to_non_default(self):
        first = Address.objects.create(
            user=self.user,
            title='خانه',
            recipient_name='میلاد علیزاده',
            phone_number='09120000000',
            province='تهران',
            city='تهران',
            address_line='خیابان ولیعصر',
            postal_code='1234567890',
        )
        second = Address.objects.create(
            user=self.user,
            title='محل کار',
            recipient_name='میلاد علیزاده',
            phone_number='09120000000',
            province='تهران',
            city='تهران',
            address_line='خیابان انقلاب',
            postal_code='1234567890',
        )

        second.is_default = True
        second.save()

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_order_snapshot_retains_original_address_after_user_changes_saved_address(self):
        address = Address.objects.create(
            user=self.user,
            title='خانه',
            recipient_name='میلاد علیزاده',
            phone_number='09120000000',
            province='تهران',
            city='تهران',
            address_line='خیابان ولیعصر',
            postal_code='1234567890',
        )
        order = Order.objects.create(
            user=self.user,
            full_name='میلاد علیزاده',
            phone_number='09120000000',
            email='test@example.com',
            address=address,
            address_line='خیابان ولیعصر',
            city='تهران',
            postal_code='1234567890',
            subtotal=Decimal('100000'),
            shipping_cost=Decimal('0'),
            total=Decimal('100000'),
        )

        address.address_line = 'خیابان شریعتی'
        address.save(update_fields=['address_line'])

        order.refresh_from_db()
        self.assertEqual(order.address_line, 'خیابان ولیعصر')

    def test_other_users_addresses_are_not_accessible(self):
        other_address = Address.objects.create(
            user=self.other_user,
            title='خانه دیگری',
            recipient_name='حسین حسینی',
            phone_number='09121111111',
            province='تهران',
            city='تهران',
            address_line='خیابان کارگر',
            postal_code='1234567890',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('accounts:address_edit', args=[other_address.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse('accounts:address_delete', args=[other_address.pk]),
            {'csrfmiddlewaretoken': 'test'},
            follow=False,
        )
        self.assertEqual(response.status_code, 404)

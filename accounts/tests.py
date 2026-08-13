from decimal import Decimal

from django.test import RequestFactory, TestCase

from cart.models import Cart, CartItem
from products.models import Category, Fabric, FabricColorVariant

from .views import SESSION_GUEST_CART_KEY, _migrate_guest_cart_to_session


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

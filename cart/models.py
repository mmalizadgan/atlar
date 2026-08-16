from decimal import Decimal

from django.conf import settings
from django.db import models

from products.models import FabricColorVariant


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
        verbose_name='کاربر',
    )
    session_key = models.CharField(max_length=40, unique=True, db_index=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سبد خرید'
        verbose_name_plural = 'سبدهای خرید'

    def __str__(self):
        return f'سبد {self.session_key[:8]}'

    @property
    def items_qs(self):
        return self.items.select_related('variant', 'variant__fabric', 'variant__fabric__category')

    @property
    def total_items(self):
        return sum(item.quantity_meters for item in self.items_qs) or Decimal('0')

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items_qs), Decimal('0'))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(FabricColorVariant, on_delete=models.CASCADE, related_name='cart_items')
    quantity_meters = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal('1'))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('cart', 'variant')]
        verbose_name = 'آیتم سبد خرید'
        verbose_name_plural = 'آیتم‌های سبد خرید'

    def __str__(self):
        return f'{self.variant} × {self.quantity_meters}م'

    @property
    def line_total(self):
        return self.variant.fabric.price_per_meter * self.quantity_meters

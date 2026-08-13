import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from accounts.models import phone_validator
from products.models import FabricColorVariant


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'در انتظار پرداخت'
        PAID = 'paid', 'پرداخت‌شده'
        PROCESSING = 'processing', 'در حال آماده‌سازی'
        SHIPPED = 'shipped', 'ارسال‌شده'
        DELIVERED = 'delivered', 'تحویل داده‌شده'
        CANCELLED = 'cancelled', 'لغوشده'

    order_number = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)

    # اسنپ‌شات اطلاعات گیرنده در لحظه ثبت سفارش
    full_name = models.CharField('نام گیرنده', max_length=120)
    phone_number = models.CharField(max_length=11, validators=[phone_validator])
    address_line = models.CharField('آدرس', max_length=300)
    city = models.CharField('شهر', max_length=80)
    postal_code = models.CharField('کد پستی', max_length=10, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'سفارش #{self.order_number}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    @property
    def is_paid(self):
        return self.status != self.Status.PENDING_PAYMENT and self.status != self.Status.CANCELLED


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(FabricColorVariant, on_delete=models.PROTECT, related_name='order_items')

    # اسنپ‌شات — اسم کالیته/رنگ و قیمت لحظه خرید، حتی اگه بعداً در products تغییر کنه
    fabric_name = models.CharField(max_length=150)
    color_name = models.CharField(max_length=60, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity_meters = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal('1'))

    class Meta:
        verbose_name = 'ردیف سفارش'
        verbose_name_plural = 'ردیف‌های سفارش'

    def __str__(self):
        return f'{self.fabric_name} × {self.quantity_meters}م'

    @property
    def line_total(self):
        return self.unit_price * self.quantity_meters

    @property
    def display_name(self):
        return f'{self.fabric_name} — {self.color_name}' if self.color_name else self.fabric_name

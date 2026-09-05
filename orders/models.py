import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from accounts.models import Address, phone_validator
from products.models import FabricColorVariant


class Discount(models.Model):
    class Type(models.TextChoices):
        PERCENT = 'percent', 'درصدی'
        FIXED = 'fixed', 'ثابت'

    code = models.CharField('کد تخفیف', max_length=30, unique=True)
    description = models.CharField('توضیح', max_length=200, blank=True)
    discount_type = models.CharField('نوع تخفیف', max_length=20, choices=Type.choices, default=Type.PERCENT)
    value = models.DecimalField('مقدار تخفیف', max_digits=10, decimal_places=0, default=0)
    min_order_total = models.DecimalField('حداقل مبلغ سفارش', max_digits=12, decimal_places=0, default=0)
    max_discount = models.DecimalField('حداکثر تخفیف', max_digits=12, decimal_places=0, default=0)
    is_active = models.BooleanField('فعال', default=True)
    valid_from = models.DateTimeField('شروع اعتبار', null=True, blank=True)
    valid_to = models.DateTimeField('پایان اعتبار', null=True, blank=True)
    usage_limit = models.PositiveIntegerField('محدودیت استفاده', default=0)
    used_count = models.PositiveIntegerField('تعداد استفاده', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تخفیف'
        verbose_name_plural = 'تخفیف‌ها'

    def __str__(self):
        return self.code


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = 'pending_payment', 'در انتظار پرداخت'
        PAID = 'paid', 'پرداخت‌شده'
        PROCESSING = 'processing', 'در حال آماده‌سازی'
        SHIPPED = 'shipped', 'ارسال‌شده'
        DELIVERED = 'delivered', 'تحویل داده‌شده'
        CANCELLED = 'cancelled', 'لغوشده'

    order_number = models.CharField(max_length=20, unique=True, editable=False, blank=True)  # ⚠️ قبلاً 12 بود ولی 14/20 کاراکتر تولید می‌شد → DataError در هر checkout
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)

    # اسنپ‌شات اطلاعات گیرنده در لحظه ثبت سفارش
    full_name = models.CharField('نام گیرنده', max_length=120)
    phone_number = models.CharField(max_length=11, validators=[phone_validator])
    email = models.EmailField('ایمیل', max_length=255, blank=True, default='')
    address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        related_name='orders',
        null=True,
        blank=True,
        verbose_name='آدرس ثبت‌شده',
    )
    address_line = models.CharField('آدرس', max_length=300, blank=True, default='')
    city = models.CharField('شهر', max_length=80, blank=True, default='')
    postal_code = models.CharField('کد پستی', max_length=10, blank=True, default='')
    tracking_code = models.CharField('کد رهگیری', max_length=80, blank=True, default='')

    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    discount = models.ForeignKey(
        Discount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='تخفیف اعمال‌شده',
    )
    discount_amount = models.DecimalField('مبلغ تخفیف', max_digits=12, decimal_places=0, default=0)
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
            # ⚠️ اصلاح: ۱۰ کاراکتر از uuid4 فقط ۴۰ بیت تصادفی است و با یک
            # IntegrityError (خطای ۵۰۰) تمام می‌شود. حالا ۱۴ کاراکتر (۵۶ بیت)
            # + تلاش مجدد در برابر تصادم.
            for _ in range(5):
                candidate = uuid.uuid4().hex[:14].upper()
                if not Order.objects.filter(order_number=candidate).exists():
                    self.order_number = candidate
                    break
            else:  # pragma: no cover - احتمال ناچیز
                self.order_number = uuid.uuid4().hex[:20].upper()
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

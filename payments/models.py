from django.db import models

from orders.models import Order


class Payment(models.Model):
    class Status(models.TextChoices):
        INITIATED = 'initiated', 'شروع‌شده'
        SUCCESS = 'success', 'موفق'
        FAILED = 'failed', 'ناموفق'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    gateway = models.CharField(max_length=30, default='zarinpal')
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.INITIATED)

    gateway_token = models.CharField(max_length=100, blank=True, db_index=True, help_text='توکن/شناسه ایجاد تراکنش از درگاه')
    gateway_ref_id = models.CharField(max_length=100, blank=True, help_text='کد پیگیری نهایی بعد از تایید پرداخت')
    raw_response = models.JSONField(blank=True, null=True, help_text='پاسخ خام درگاه، برای دیباگ')

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'تراکنش پرداخت'
        verbose_name_plural = 'تراکنش‌های پرداخت'
        ordering = ['-created_at']

    def __str__(self):
        return f'پرداخت سفارش {self.order.order_number} - {self.get_status_display()}'

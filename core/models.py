from django.core.cache import cache
from django.db import models


class SiteSettings(models.Model):
    """
    تنظیمات عمومی سایت — یک رکورد تکی که از پنل ادمین قابل ویرایشه،
    بدون نیاز به تغییر کد (اسم فروشگاه، شبکه‌های اجتماعی، هزینه ارسال و ...).
    """
    site_name = models.CharField(max_length=80, default='آتلار')
    tagline = models.CharField(max_length=200, blank=True, default='پارچه مبلی، مستقیم از تولید تا خانه شما')
    about_text = models.TextField(blank=True)
    phone_display = models.CharField('شماره تماس نمایشی', max_length=20, blank=True)
    instagram_username = models.CharField(max_length=60, blank=True)
    telegram_username = models.CharField(max_length=60, blank=True)
    address = models.CharField(max_length=255, blank=True)

    default_fabric_width_cm = models.PositiveSmallIntegerField(
        'عرض رول پارچه (سانتی‌متر)', default=140,
        help_text='عرض طاقه برای همه‌ی پارچه‌های فروشگاه ثابته — فقط همین یک‌جا تنظیمش کن.',
    )

    default_shipping_cost = models.DecimalField('هزینه ارسال (تومان)', max_digits=10, decimal_places=0, default=0)
    free_shipping_threshold = models.DecimalField(
        'حداقل خرید برای ارسال رایگان (تومان)', max_digits=10, decimal_places=0,
        null=True, blank=True,
        help_text='خالی بگذار اگر ارسال رایگان نداری.',
    )

    class Meta:
        verbose_name = 'تنظیمات سایت'
        verbose_name_plural = 'تنظیمات سایت'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1  # همیشه فقط یک رکورد
        super().save(*args, **kwargs)
        cache.delete('site_settings')

    @classmethod
    def load(cls):
        settings_obj = cache.get('site_settings')
        if settings_obj is None:
            settings_obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('site_settings', settings_obj, 60 * 30)
        return settings_obj

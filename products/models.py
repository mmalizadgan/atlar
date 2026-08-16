from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import uuid


def unique_slug(instance, base_value, slug_field='slug'):
    slug = slugify(base_value, allow_unicode=True) or uuid.uuid4().hex[:8]
    ModelClass = instance.__class__
    candidate = slug
    i = 1
    while ModelClass.objects.filter(**{slug_field: candidate}).exclude(pk=instance.pk).exists():
        i += 1
        candidate = f'{slug}-{i}'
    return candidate


class Category(models.Model):
    name = models.CharField('نام دسته', max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:category_detail', kwargs={'category_slug': self.slug})


class FabricQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def in_stock(self):
        return self.filter(color_variants__stock_meters__gt=0).distinct()

    def with_gallery(self):
        return self.select_related('category').prefetch_related('color_variants', 'color_variants__images')


class Fabric(models.Model):
    """
    «کالیته» — نوع/طرح پارچه. مشخصات مشترک بین همه‌ی رنگ‌بندی‌های این کالیته
    اینجاست؛ رنگ، تصویر و موجودی مال هر رنگ‌بندی جداگانه‌ست (FabricColorVariant).
    """
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='fabrics', verbose_name='دسته‌بندی')
    name = models.CharField('نام کالیته', max_length=150)
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True, blank=True)
    sku = models.CharField('کد کالا', max_length=40, unique=True, blank=True)
    description = models.TextField('توضیحات', blank=True)

    pattern = models.CharField('طرح', max_length=60, blank=True, help_text='مثلاً: ساده، طرح‌دار، گلدار، هندسی')
    material = models.CharField('جنس', max_length=120, blank=True, help_text='مثلاً: ۱۰۰٪ پلی‌استر')
    abrasion_rating = models.PositiveIntegerField(
        'مقاومت سایش (مارتیندل)', null=True, blank=True,
        help_text='تعداد چرخه تست مارتیندل — هرچه بیشتر، بادوام‌تر.',
    )
    is_washable = models.BooleanField('قابل شست‌وشو', default=False)

    price_per_meter = models.DecimalField('قیمت هر متر (تومان)', max_digits=12, decimal_places=0)
    min_order_meters = models.DecimalField('حداقل سفارش (متر)', max_digits=4, decimal_places=1, default=Decimal('1'))

    is_active = models.BooleanField('فعال / نمایش در سایت', default=True)
    is_featured = models.BooleanField('محصول ویژه', default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FabricQuerySet.as_manager()

    class Meta:
        verbose_name = 'کالیته پارچه'
        verbose_name_plural = 'کالیته‌های پارچه'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'category']),
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        if not self.sku:
            self.sku = f'ATL-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('products:fabric_detail', kwargs={'slug': self.slug})

    @property
    def active_variants(self):
        # روی یک queryset پریفچ‌شده هم بدون کوئری اضافه کار می‌کنه
        return [v for v in self.color_variants.all() if v.is_active]

    @property
    def default_variant(self):
        variants = self.active_variants
        return variants[0] if variants else None

    @property
    def in_stock(self):
        return any(v.stock_meters > 0 for v in self.active_variants)

    @property
    def total_stock(self):
        return sum((v.stock_meters for v in self.active_variants), Decimal('0'))

    @property
    def price_display(self):
        return f'{int(self.price_per_meter):,} تومان / متر'


class FabricColorVariant(models.Model):
    """یک رنگ‌بندی مشخص از یک کالیته — واحد واقعی خرید (SKU)."""
    fabric = models.ForeignKey(Fabric, on_delete=models.CASCADE, related_name='color_variants', verbose_name='کالیته')
    color_name = models.CharField('نام رنگ', max_length=60)
    color_hex = models.CharField(
        'کد رنگ (اختیاری)', max_length=7, blank=True,
        help_text='برای نمایش دایره‌ی رنگ، مثلاً #7a1f2b — خالی بگذار اگر نمی‌دونی.',
    )
    image = models.ImageField('تصویر این رنگ', upload_to='fabrics/variants/', blank=True, null=True)
    stock_meters = models.DecimalField('موجودی (متر)', max_digits=8, decimal_places=1, default=Decimal('0'))
    order = models.PositiveSmallIntegerField('ترتیب نمایش', default=0)
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رنگ‌بندی'
        verbose_name_plural = 'رنگ‌بندی‌ها'
        ordering = ['order', 'id']
        unique_together = [('fabric', 'color_name')]

    def __str__(self):
        return f'{self.fabric.name} — {self.color_name}'

    @property
    def in_stock(self):
        return self.stock_meters > 0


class FabricImage(models.Model):
    variant = models.ForeignKey(FabricColorVariant, on_delete=models.CASCADE, related_name='images', verbose_name='رنگ‌بندی')
    image = models.ImageField(upload_to='fabrics/gallery/')
    alt_text = models.CharField(max_length=150, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'تصویر گالری'
        verbose_name_plural = 'تصاویر گالری'

    def __str__(self):
        return f'{self.variant} - {self.order}'

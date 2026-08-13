from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Fabric, FabricColorVariant, FabricImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active', 'fabric_count']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    @admin.display(description='تعداد کالیته‌ها')
    def fabric_count(self, obj):
        return obj.fabrics.count()


class FabricImageInline(admin.TabularInline):
    model = FabricImage
    extra = 2
    fields = ['image', 'preview', 'alt_text', 'order']
    readonly_fields = ['preview']

    @admin.display(description='پیش‌نمایش')
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:6px;" />', obj.image.url)
        return '—'


@admin.register(FabricColorVariant)
class FabricColorVariantAdmin(admin.ModelAdmin):
    """
    صفحه‌ی مستقل هر رنگ‌بندی — برای وقتی که می‌خوای برای یک رنگ خاص
    چند تا عکس گالری (از زوایای مختلف) اضافه کنی. برای افزودن سریع
    رنگ‌های یک کالیته، از خودِ صفحه‌ی «کالیته» در ادمین استفاده کن.
    """
    list_display = ['thumbnail', 'fabric', 'color_name', 'stock_meters', 'is_active', 'order']
    list_display_links = ['thumbnail', 'color_name']
    list_editable = ['stock_meters', 'is_active', 'order']
    list_filter = ['is_active', 'fabric__category']
    search_fields = ['color_name', 'fabric__name']
    autocomplete_fields = ['fabric']
    inlines = [FabricImageInline]

    @admin.display(description='تصویر')
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:6px;" />', obj.image.url)
        return '—'


class FabricColorVariantInline(admin.TabularInline):
    """افزودن سریع چند رنگ‌بندی مستقیم از صفحه‌ی کالیته."""
    model = FabricColorVariant
    extra = 1
    fields = ['color_name', 'color_hex', 'image', 'stock_meters', 'order', 'is_active']
    show_change_link = True


@admin.register(Fabric)
class FabricAdmin(admin.ModelAdmin):
    list_display = [
        'thumbnail', 'name', 'category', 'price_per_meter',
        'variant_count', 'total_stock_display', 'is_active', 'is_featured', 'updated_at',
    ]
    list_display_links = ['thumbnail', 'name']
    list_editable = ['price_per_meter', 'is_active', 'is_featured']
    list_filter = ['category', 'is_active', 'is_featured', 'is_fire_retardant', 'is_washable']
    search_fields = ['name', 'sku', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'sku']
    list_select_related = ['category']
    list_per_page = 30
    inlines = [FabricColorVariantInline]
    save_on_top = True

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'slug', 'category', 'sku', 'description'),
        }),
        ('مشخصات پارچه', {
            'fields': ('pattern', 'material', 'abrasion_rating', 'is_fire_retardant', 'is_washable'),
            'description': 'عرض رول از «تنظیمات سایت» (Core → Site settings) کنترل می‌شه، چون برای همه‌ی پارچه‌ها ثابته.',
        }),
        ('قیمت', {
            'fields': ('price_per_meter', 'min_order_meters'),
        }),
        ('نمایش در سایت', {
            'fields': ('is_active', 'is_featured'),
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='تصویر')
    def thumbnail(self, obj):
        variant = obj.default_variant
        if variant and variant.image:
            return format_html('<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:6px;" />', variant.image.url)
        return '—'

    @admin.display(description='تعداد رنگ‌بندی')
    def variant_count(self, obj):
        return obj.color_variants.count()

    @admin.display(description='مجموع موجودی (متر)')
    def total_stock_display(self, obj):
        return obj.total_stock

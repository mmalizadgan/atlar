from django.contrib import admin

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('عمومی', {'fields': ('site_name', 'tagline', 'about_text')}),
        ('ارتباط با ما', {'fields': ('phone_display', 'instagram_username', 'telegram_username', 'address')}),
        ('مشخصات ثابت پارچه‌ها', {'fields': ('default_fabric_width_cm',)}),
        ('ارسال', {'fields': ('default_shipping_cost', 'free_shipping_threshold')}),
    )

    def has_add_permission(self, request):
        # فقط یک رکورد تنظیمات باید وجود داشته باشه
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        from django.shortcuts import redirect
        return redirect('admin:core_sitesettings_change', obj.pk)

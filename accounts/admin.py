from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, OTP, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['-date_joined']
    list_display = ['phone_number', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined']
    search_fields = ['phone_number', 'first_name', 'last_name']
    readonly_fields = ['date_joined']

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name')}),
        ('دسترسی‌ها', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تاریخ‌ها', {'fields': ('date_joined',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )
    filter_horizontal = ['groups', 'user_permissions']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'recipient_name', 'city', 'phone_number', 'is_default', 'created_at']
    list_filter = ['is_default', 'province', 'city', 'created_at']
    search_fields = ['user__phone_number', 'user__first_name', 'user__last_name', 'recipient_name', 'city', 'address_line']
    readonly_fields = ['created_at']
    fieldsets = (
        ('کاربر', {'fields': ('user', 'title', 'is_default')}),
        ('گیرنده', {'fields': ('recipient_name', 'phone_number')}),
        ('موقعیت', {'fields': ('province', 'city', 'address_line', 'postal_code', 'plate', 'unit')}),
        ('توضیحات', {'fields': ('notes',)}),
        ('تاریخ', {'fields': ('created_at',)}),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """
    ⚠️ اصلاح: ستون `code` حذف شد. کد یک‌بارمصرف به‌صورت هش ذخیره می‌شود و
    هیچ‌کس (حتی ادمین) نمی‌تواند با دیدن رکورد، وارد حساب کاربر شود.
    """
    list_display = ['phone_number', 'created_at', 'expires_at', 'is_used', 'attempts']
    list_filter = ['is_used', 'created_at']
    search_fields = ['phone_number']
    readonly_fields = ['phone_number', 'code_hash', 'session_key', 'created_at',
                       'expires_at', 'is_used', 'attempts', 'verified_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # رکورد OTP فقط خواندنی است — دست‌کاری آن یعنی جعل احراز هویت.
        return False

    def has_delete_permission(self, request, obj=None):
        # حذف انبوه برای پاک‌سازی مجاز است.
        return request.user.is_superuser

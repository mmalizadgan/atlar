from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'gateway', 'amount', 'status', 'gateway_ref_id', 'created_at', 'verified_at']
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['order__order_number', 'gateway_token', 'gateway_ref_id']
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

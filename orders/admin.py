from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['variant', 'fabric_name', 'color_name', 'unit_price', 'quantity_meters', 'line_total']
    can_delete = False

    @admin.display(description='جمع ردیف')
    def line_total(self, obj):
        return f'{int(obj.line_total):,} تومان'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'full_name', 'phone_number', 'city', 'total', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'city']
    search_fields = ['order_number', 'full_name', 'phone_number']
    readonly_fields = ['order_number', 'user', 'subtotal', 'shipping_cost', 'total', 'created_at', 'updated_at']
    list_editable = ['status']
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]

    fieldsets = (
        ('سفارش', {'fields': ('order_number', 'user', 'status')}),
        ('گیرنده', {'fields': ('full_name', 'phone_number', 'city', 'address_line', 'postal_code')}),
        ('مبالغ', {'fields': ('subtotal', 'shipping_cost', 'total')}),
        ('تاریخ‌ها', {'fields': ('created_at', 'updated_at')}),
    )

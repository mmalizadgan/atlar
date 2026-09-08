from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from core.models import SiteSettings
from products.models import FabricColorVariant

from .forms import CheckoutForm
from .models import Order, OrderItem


def _calculate_shipping(subtotal):
    settings_obj = SiteSettings.load()
    threshold = settings_obj.free_shipping_threshold
    if threshold and subtotal >= threshold:
        return 0
    return settings_obj.default_shipping_cost


# ---------------------------------------------------------------------------
# ⚠️ اصلاح امنیتی/صحت: رزرو موجودی با قفل ردیف (select_for_update)
# قبلاً موجودی فقط «چک» می‌شد؛ دو کاربر همزمان می‌توانستند هرکدام ۲۰ متر از
# موجودیِ ۲۰ متری بخرند (oversell / race condition).
# ---------------------------------------------------------------------------
def _reserve_stock(items):
    """
    موجودی را برای آیتم‌های سبد قفل و کسر می‌کند.
    در صورت کمبود، (آیتمِ مشکل‌دار) را برمی‌گرداند تا پیام درست نشان داده شود.
    """
    variant_ids = [item.variant_id for item in items]
    locked_variants = {
        variant.pk: variant
        for variant in FabricColorVariant.objects.select_for_update().filter(pk__in=variant_ids)
    }
    for item in items:
        variant = locked_variants.get(item.variant_id)
        if variant is None or not variant.is_active:
            return item
        if variant.stock_meters < item.quantity_meters:
            return item
    for item in items:
        FabricColorVariant.objects.filter(pk=item.variant_id).update(
            stock_meters=F('stock_meters') - item.quantity_meters
        )
    return None


def release_order_stock(order):
    """بازگرداندن موجودی رزروشده (وقتی سفارش لغو یا پرداختش ناموفق می‌شود)."""
    with transaction.atomic():
        for item in order.items.select_related('variant'):
            if item.variant_id:
                FabricColorVariant.objects.filter(pk=item.variant_id).update(
                    stock_meters=F('stock_meters') + item.quantity_meters
                )


@login_required
def checkout_view(request):
    cart = request.cart
    if not cart or cart.items.count() == 0:
        messages.warning(request, 'سبد خریدت خالیه.')
        return redirect('cart:detail')

    initial = {'full_name': request.user.get_full_name(), 'phone_number': request.user.phone_number}

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            subtotal = cart.subtotal
            shipping_cost = _calculate_shipping(subtotal)
            try:
                with transaction.atomic():
                    # موجودی در همان تراکنش و با قفل ردیف کسر می‌شود.
                    out_of_stock = _reserve_stock(list(cart.items_qs))
                    if out_of_stock is not None:
                        raise ValueError(
                            f'موجودی «{out_of_stock.variant.fabric.name} — '
                            f'{out_of_stock.variant.color_name}» کافی نیست.'
                        )

                    order = Order.objects.create(
                        user=request.user,
                        full_name=form.cleaned_data['full_name'],
                        phone_number=form.cleaned_data['phone_number'],
                        email=form.cleaned_data.get('email', ''),
                        address_line=form.cleaned_data['address_line'],
                        city=form.cleaned_data['city'],
                        postal_code=form.cleaned_data['postal_code'],
                        subtotal=subtotal,
                        shipping_cost=shipping_cost,
                        total=subtotal + shipping_cost,
                    )
                    OrderItem.objects.bulk_create([
                        OrderItem(
                            order=order, variant=item.variant, fabric_name=item.variant.fabric.name,
                            color_name=item.variant.color_name,
                            unit_price=item.variant.fabric.price_per_meter,
                            quantity_meters=item.quantity_meters,
                        )
                        for item in cart.items_qs
                    ])
                    # سبد همان‌جا خالی می‌شود (قبلاً فقط بعد از پرداخت موفق خالی می‌شد
                    # و اگر callback درگاه با نشست درستی نمی‌رسید، سبد پر می‌ماند).
                    cart.items.all().delete()
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('cart:detail')

            return redirect(
                'payments:initiate_with_gateway',
                order_number=order.order_number,
                gateway=form.cleaned_data['gateway'],
            )
    else:
        form = CheckoutForm(initial=initial)

    shipping_estimate = _calculate_shipping(cart.subtotal)
    return render(request, 'orders/checkout.html', {
        'form': form, 'cart': cart, 'items': cart.items_qs,
        'shipping_estimate': shipping_estimate,
    })


@login_required
def order_success_view(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'orders/order_history.html', {'orders': orders})


@login_required
def order_detail_view(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related('items'), order_number=order_number, user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def order_cancel_view(request, order_number):
    """
    جدید: لغو سفارش پرداخت‌نشده + بازگرداندن موجودی (با قفل و بدون دوباره‌کسر شدن).
    """
    if request.method != 'POST':
        return redirect('orders:detail', order_number=order_number)

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number, user=request.user,
        )
        if order.status != Order.Status.PENDING_PAYMENT:
            messages.error(request, 'این سفارش قابل لغو نیست.')
            return redirect('orders:detail', order_number=order.order_number)
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])

    release_order_stock(order)
    messages.info(request, 'سفارش لغو شد و موجودی به انبار برگشت.')
    return redirect('orders:history')

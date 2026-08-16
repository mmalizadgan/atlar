from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.models import SiteSettings

from .forms import CheckoutForm
from .models import Order, OrderItem


def _calculate_shipping(subtotal):
    settings_obj = SiteSettings.load()
    threshold = settings_obj.free_shipping_threshold
    if threshold and subtotal >= threshold:
        return 0
    return settings_obj.default_shipping_cost


@login_required
def checkout_view(request):
    cart = request.cart
    if not cart or cart.items.count() == 0:
        messages.warning(request, 'سبد خریدت خالیه.')
        return redirect('cart:detail')

    # چک نهایی موجودی قبل از ثبت سفارش (ممکنه از زمان افزودن به سبد موجودی تغییر کرده باشه)
    for item in cart.items_qs:
        if item.quantity_meters > item.variant.stock_meters:
            messages.error(request, f'موجودی «{item.variant.fabric.name} — {item.variant.color_name}» کافی نیست (فقط {item.variant.stock_meters} متر مونده).')
            return redirect('cart:detail')

    initial = {'full_name': request.user.get_full_name(), 'phone_number': request.user.phone_number}

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            subtotal = cart.subtotal
            shipping_cost = _calculate_shipping(subtotal)
            with transaction.atomic():
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
                        unit_price=item.variant.fabric.price_per_meter, quantity_meters=item.quantity_meters,
                    )
                    for item in cart.items_qs
                ])
            return redirect('payments:initiate', order_number=order.order_number)
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

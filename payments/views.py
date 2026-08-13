from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from products.models import Fabric

from .gateways.bale_pay import BalePayGateway, get_callback_url
from .models import Payment


@login_required
def initiate_payment_view(request, order_number):
    order = get_object_or_404(
        Order, order_number=order_number, user=request.user, status=Order.Status.PENDING_PAYMENT,
    )
    payment = Payment.objects.create(order=order, amount=order.total)

    gateway = BalePayGateway()
    try:
        result = gateway.request_payment(order, callback_url=get_callback_url(request))
    except Exception:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        messages.error(
            request,
            'اتصال به درگاه بله‌پی هنوز کامل نشده (احتمالاً BALE_PAY_MERCHANT_ID / '
            'BALE_PAY_API_KEY در .env خالیه یا آدرس API نهایی نشده). سفارشت ذخیره‌ست، '
            'بعد از تنظیم درگاه می‌تونی دوباره تلاش کنی.',
        )
        return redirect('orders:detail', order_number=order.order_number)

    payment.gateway_token = result.token
    payment.save(update_fields=['gateway_token'])
    return redirect(result.redirect_url)


@csrf_exempt
def bale_callback_view(request):
    gateway = BalePayGateway()
    result = gateway.verify_payment(request)

    token = request.GET.get('token') or request.POST.get('token', '')
    payment = get_object_or_404(Payment, gateway_token=token) if token else None

    if payment is None:
        messages.error(request, 'تراکنش پیدا نشد.')
        return redirect('core:home')

    order = payment.order

    if result.success:
        with transaction.atomic():
            payment.status = Payment.Status.SUCCESS
            payment.gateway_ref_id = result.ref_id
            payment.raw_response = result.raw_response
            payment.verified_at = timezone.now()
            payment.save()

            order.status = Order.Status.PAID
            order.save(update_fields=['status'])

            for item in order.items.all():
                Fabric.objects.filter(pk=item.fabric_id).update(
                    stock_meters=F('stock_meters') - item.quantity_meters
                )

            cart = request.cart
            if cart:
                cart.items.all().delete()

        messages.success(request, 'پرداخت با موفقیت انجام شد. سفارشت ثبت شد 🎉')
        return redirect('orders:success', order_number=order.order_number)

    payment.status = Payment.Status.FAILED
    payment.raw_response = result.raw_response
    payment.save(update_fields=['status', 'raw_response'])
    messages.error(request, result.message or 'پرداخت ناموفق بود. سفارشت هنوز فعاله، می‌تونی دوباره تلاش کنی.')
    return redirect('orders:detail', order_number=order.order_number)

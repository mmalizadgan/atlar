import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from orders.models import Order
from orders.views import release_order_stock

from .gateways.bale_pay import BalePayGateway, get_callback_url
from .models import Payment

logger = logging.getLogger('payments')

# حداکثر تعداد تراکنش «شروع‌شده» برای هر سفارش (ضد پرکردن جدول Payment)
MAX_OPEN_PAYMENTS_PER_ORDER = 3


@login_required
@require_http_methods(['GET', 'POST'])
def initiate_payment_view(request, order_number):
    order = get_object_or_404(
        Order, order_number=order_number, user=request.user, status=Order.Status.PENDING_PAYMENT,
    )

    # ⚠️ اصلاح: به‌جای ساختن بی‌نهایت رکورد Payment، تراکنش باز قبلی را
    # دوباره استفاده می‌کنیم و فقط تا سقف مشخص رکورد جدید می‌سازیم.
    payment = (
        Payment.objects.filter(
            order=order, status=Payment.Status.INITIATED, gateway_token=''
        ).order_by('-created_at').first()
    )
    if payment is None:
        open_count = Payment.objects.filter(
            order=order, status=Payment.Status.INITIATED
        ).count()
        if open_count >= MAX_OPEN_PAYMENTS_PER_ORDER:
            messages.error(request, 'تعداد تلاش‌های پرداخت برای این سفارش زیاد است. با پشتیبانی تماس بگیر.')
            return redirect('orders:detail', order_number=order.order_number)
        payment = Payment.objects.create(order=order, amount=order.total)

    gateway = BalePayGateway()
    try:
        result = gateway.request_payment(order, callback_url=get_callback_url(request))
    except Exception:
        logger.exception('payment initiation failed (order=%s)', order.order_number)
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        messages.error(
            request,
            'اتصال به درگاه بله‌پی هنوز کامل نشده (احتمالاً BALE_PAY_MERCHANT_ID / '
            'BALE_PAY_API_KEY در .env خالیه یا آدرس API نهایی نشده). سفارشت ذخیره‌ست، '
            'بعد از تنظیم درگاه می‌تونی دوباره تلاش کن.',
        )
        return redirect('orders:detail', order_number=order.order_number)

    payment.gateway_token = result.token
    payment.save(update_fields=['gateway_token'])
    return redirect(result.redirect_url)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def bale_callback_view(request):
    """
    ⚠️ اصلاحات مهم در callback درگاه:
      ۱) idempotent شد — تکرار callback دیگر موجودی را دوباره کسر/سفارش را دوباره
         «پرداخت‌شده» نمی‌کند (قبلاً هر بار callback، موجودی یک‌بار دیگر کم می‌شد).
      ۲) با قفل ردیف (select_for_update) → دو callback همزمان عملاً یکی اجرا می‌شود.
      ۳) مبلغ تاییدشده‌ی درگاه با مبلغ سفارش مقایسه می‌شود (ضد پرداخت ناقص/جعل).
      ۴) موجودی دیگر اینجا کسر نمی‌شود؛ رزرو در checkout انجام می‌شود.
         (کد قبلی `item.fabric_id` نداشت → AttributeError و موجودی هیچ‌وقت کم نمی‌شد.)
      ۵) خطای درگاه دیگر ۵۰۰ نمی‌دهد.
    """
    gateway = BalePayGateway()
    result = gateway.verify_payment(request)

    token = (request.GET.get('token') or request.POST.get('token') or '').strip()
    if not token:
        messages.error(request, 'تراکنش پیدا نشد.')
        return redirect('core:home')

    payment = Payment.objects.filter(gateway_token=token).first()
    if payment is None:
        messages.error(request, 'تراکنش پیدا نشد.')
        return redirect('core:home')

    order = payment.order

    with transaction.atomic():
        # قفل ردیف: دو callback همزمان فقط یکی‌شان به پردازش می‌رسند.
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        order = Order.objects.select_for_update().get(pk=order.pk)

        if payment.status == Payment.Status.SUCCESS:
            # قبلاً تایید شده است → فقط ریدایرکت، بدون هیچ تغییر داده‌ای.
            return redirect('orders:success', order_number=order.order_number)

        if not result.success:
            payment.status = Payment.Status.FAILED
            payment.raw_response = result.raw_response
            payment.save(update_fields=['status', 'raw_response'])
            # موجودی رزروشده به انبار برمی‌گردد و سفارش قابل ثبت مجدد است.
            release_order_stock(order)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            messages.error(
                request,
                result.message or 'پرداخت ناموفق بود. می‌تونی سفارش رو دوباره ثبت کنی.',
            )
            return redirect('orders:history')

        # ✅ تایید موفق — بررسی مبلغ: حتماً باید با مبلغ سفارش یکی باشد.
        if result.amount is not None and int(result.amount) != int(payment.amount):
            payment.status = Payment.Status.FAILED
            payment.raw_response = {'error': 'amount_mismatch',
                                    'gateway_amount': result.amount}
            payment.save(update_fields=['status', 'raw_response'])
            release_order_stock(order)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            logger.error(
                'amount mismatch for order %s (expected=%s got=%s)',
                order.order_number, payment.amount, result.amount,
            )
            messages.error(request, 'مبلغ پرداخت‌شده با مبلغ سفارش همخوانی ندارد. با پشتیبانی تماس بگیر.')
            return redirect('orders:history')

        if order.status != Order.Status.PENDING_PAYMENT:
            # سفارش قبلاً پرداخت/لغو شده؛ تراکنش را ثبت می‌کنیم ولی موجودی دست نمی‌زنیم.
            payment.status = Payment.Status.SUCCESS
            payment.gateway_ref_id = result.ref_id
            payment.verified_at = timezone.now()
            payment.save(update_fields=['status', 'gateway_ref_id', 'verified_at'])
            return redirect('orders:success', order_number=order.order_number)

        payment.status = Payment.Status.SUCCESS
        payment.gateway_ref_id = result.ref_id
        payment.raw_response = result.raw_response
        payment.verified_at = timezone.now()
        payment.save(update_fields=[
            'status', 'gateway_ref_id', 'raw_response', 'verified_at',
        ])

        order.status = Order.Status.PAID
        order.save(update_fields=['status'])

    messages.success(request, 'پرداخت با موفقیت انجام شد. سفارشت ثبت شد 🎉')
    return redirect('orders:success', order_number=order.order_number)

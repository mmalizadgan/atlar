import json
import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from orders.models import Order
from orders.views import release_order_stock

from .gateways.balepay import BalePayGateway
from .gateways.zarinpal import ZarinpalGateway, get_callback_url
from .models import Payment

logger = logging.getLogger('payments')

# حداکثر تعداد تراکنش «شروع‌شده» برای هر سفارش (ضد پرکردن جدول Payment)
MAX_OPEN_PAYMENTS_PER_ORDER = 3


@login_required
@require_http_methods(['GET', 'POST'])
def initiate_payment_view(request, order_number, gateway='zarinpal'):
    order = get_object_or_404(
        Order, order_number=order_number, user=request.user, status=Order.Status.PENDING_PAYMENT,
    )

    if gateway not in {'zarinpal', 'balepay'}:
        messages.error(request, 'روش پرداخت انتخاب‌شده معتبر نیست.')
        return redirect('orders:detail', order_number=order.order_number)

    chat_id = request.session.get('balepay_chat_id', '')
    if gateway == 'balepay' and not chat_id:
        return redirect('payments:connect', order_number=order.order_number, gateway='balepay')

    # ⚠️ اصلاح: به‌جای ساختن بی‌نهایت رکورد Payment، تراکنش باز قبلی را
    # دوباره استفاده می‌کنیم و فقط تا سقف مشخص رکورد جدید می‌سازیم.
    payment = (
        Payment.objects.filter(
            order=order, status=Payment.Status.INITIATED, gateway=gateway, gateway_token=''
        ).order_by('-created_at').first()
    )
    if payment is None:
        open_count = Payment.objects.filter(
            order=order, status=Payment.Status.INITIATED, gateway=gateway
        ).count()
        if open_count >= MAX_OPEN_PAYMENTS_PER_ORDER:
            messages.error(request, 'تعداد تلاش‌های پرداخت برای این سفارش زیاد است. با پشتیبانی تماس بگیر.')
            return redirect('orders:detail', order_number=order.order_number)
        payment = Payment.objects.create(order=order, amount=order.total, gateway=gateway)

    gateway_client = BalePayGateway(chat_id=chat_id) if gateway == 'balepay' else ZarinpalGateway()
    try:
        callback_url = get_callback_url(request) if gateway == 'zarinpal' else ''
        result = gateway_client.request_payment(order, callback_url=callback_url)
    except Exception as exc:
        logger.exception('payment initiation failed (order=%s)', order.order_number)
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=['status'])
        detail = f' جزئیات: {exc}' if settings.DEBUG else ''
        messages.error(
            request,
            f'شروع پرداخت با {"بله‌پی" if gateway == "balepay" else "زرین‌پال"} ناموفق بود.{detail} '
            'سفارشت ذخیره‌ست، بعد از تنظیم درگاه می‌تونی دوباره تلاش کن.',
        )
        return redirect('orders:detail', order_number=order.order_number)

    payment.gateway_token = result.token
    if gateway == 'balepay':
        payment.raw_response = {'chat_id': chat_id}
        payment.save(update_fields=['gateway_token', 'raw_response'])
        return render(request, 'payments/waiting.html', {'order': order})
    payment.save(update_fields=['gateway_token'])
    return redirect(result.redirect_url)


@login_required
def balepay_connect_view(request, order_number, gateway='balepay'):
    order = get_object_or_404(
        Order, order_number=order_number, user=request.user, status=Order.Status.PENDING_PAYMENT,
    )
    code = secrets.token_urlsafe(18).replace('-', '').replace('_', '')[:24]
    cache.set(f'balepay:connect:{code}', {
        'session_key': request.session.session_key,
    }, timeout=15 * 60)
    bot_username = str(getattr(settings, 'BALEPAY_BOT_USERNAME', '') or '').strip().lstrip('@')
    link = f'https://ble.ir/{bot_username}?start={code}' if bot_username else ''
    return render(request, 'payments/connect.html', {
        'order': order, 'connect_link': link, 'gateway': gateway,
    })


@login_required
def balepay_connection_status_view(request):
    chat_id = cache.get(f'balepay:session:{request.session.session_key}')
    if chat_id:
        request.session['balepay_chat_id'] = str(chat_id)
    return JsonResponse({'connected': bool(chat_id)})


@csrf_exempt
@require_http_methods(['POST'])
def balepay_webhook_view(request, secret):
    expected = str(getattr(settings, 'BALEPAY_WEBHOOK_SECRET', '') or '').strip()
    if not expected or not secrets.compare_digest(secret, expected):
        return JsonResponse({'ok': False}, status=403)
    try:
        update = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return JsonResponse({'ok': True})
    if isinstance(update.get('message'), dict):
        _handle_start_message(update['message'])
    if isinstance(update.get('pre_checkout_query'), dict):
        _handle_pre_checkout(update['pre_checkout_query'])
    if isinstance(update.get('message'), dict) and isinstance(update['message'].get('successful_payment'), dict):
        _handle_successful_payment(update['message'])
    return JsonResponse({'ok': True})


def _handle_start_message(message):
    text = str(message.get('text') or '').strip()
    if not text.startswith('/start '):
        return
    code = text.split(None, 1)[1].strip()
    connection = cache.get(f'balepay:connect:{code}')
    chat_id = str((message.get('chat') or {}).get('id') or '')
    if not connection or not chat_id or str((message.get('from') or {}).get('id') or '') != chat_id:
        return
    cache.set(f'balepay:session:{connection["session_key"]}', chat_id, timeout=30 * 24 * 3600)
    cache.delete(f'balepay:connect:{code}')


def _handle_pre_checkout(query):
    payment = Payment.objects.filter(gateway='balepay', gateway_token=query.get('invoice_payload', '')).first()
    payer_id = str((query.get('from') or {}).get('id') or '')
    stored_chat_id = str((payment.raw_response or {}).get('chat_id') or '') if payment else ''
    valid = (
        payment is not None and payment.status == Payment.Status.INITIATED
        and stored_chat_id == payer_id
        and str(query.get('currency', '')).upper() == 'IRR'
        and _amount_matches(query.get('total_amount'), payment.amount)
    )
    token = str(getattr(settings, 'BALEPAY_BOT_TOKEN', '') or '').strip()
    if not token:
        return
    payload = {'pre_checkout_query_id': query.get('id'), 'ok': valid}
    if not valid:
        payload['error_message'] = 'اطلاعات فاکتور با سفارش مطابقت ندارد.'
    try:
        import requests
        requests.post(f'https://tapi.bale.ai/bot{token}/answerPreCheckoutQuery', json=payload, timeout=(3, 10))
    except requests.RequestException:
        logger.exception('Bale pre-checkout response failed')


def _handle_successful_payment(message):
    success = message['successful_payment']
    payload = str(success.get('invoice_payload') or '')
    charge_id = str(success.get('provider_payment_charge_id') or success.get('telegram_payment_charge_id') or '')[:100]
    if not payload or not charge_id:
        return
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related('order').filter(
            gateway='balepay', gateway_token=payload,
        ).first()
        if payment is None or payment.status == Payment.Status.SUCCESS:
            return
        payer_id = str((message.get('from') or {}).get('id') or (message.get('chat') or {}).get('id') or '')
        stored_chat_id = str((payment.raw_response or {}).get('chat_id') or '')
        if (
            stored_chat_id != payer_id
            or str(success.get('currency', '')).upper() != 'IRR'
            or not _amount_matches(success.get('total_amount'), payment.amount)
        ):
            payment.status = Payment.Status.FAILED
            payment.raw_response = {'error': 'amount_or_currency_mismatch', 'event': success}
            payment.save(update_fields=['status', 'raw_response'])
            return
        payment.status = Payment.Status.SUCCESS
        payment.gateway_ref_id = charge_id
        payment.raw_response = {'successful_payment': success}
        payment.verified_at = timezone.now()
        payment.save(update_fields=['status', 'gateway_ref_id', 'raw_response', 'verified_at'])
        if payment.order.status == Order.Status.PENDING_PAYMENT:
            payment.order.status = Order.Status.PAID
            payment.order.save(update_fields=['status'])


def _amount_matches(value, amount):
    try:
        return int(value) == int(amount) * 10
    except (TypeError, ValueError):
        return False


@login_required
def balepay_payment_status_view(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    payment = Payment.objects.filter(order=order, gateway='balepay').order_by('-created_at').first()
    return JsonResponse({'paid': order.status == Order.Status.PAID, 'payment_status': payment.status if payment else ''})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def zarinpal_callback_view(request):
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
    token = (request.GET.get('Authority') or request.POST.get('Authority') or '').strip()
    if not token:
        messages.error(request, 'تراکنش پیدا نشد.')
        return redirect('core:home')

    payment = Payment.objects.filter(gateway='zarinpal', gateway_token=token).first()
    if payment is None:
        messages.error(request, 'تراکنش پیدا نشد.')
        return redirect('core:home')

    gateway = ZarinpalGateway()
    result = gateway.verify_payment(request, expected_amount=payment.amount)

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

"""Zarinpal payment gateway integration (sandbox or production)."""
import requests
from django.conf import settings
from django.urls import reverse

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult


ZARINPAL_SANDBOX_BASE_URL = 'https://sandbox.zarinpal.com'
ZARINPAL_PRODUCTION_BASE_URL = 'https://payment.zarinpal.com'


class ZarinpalGateway(PaymentGateway):
    def __init__(self):
        # sandbox بدون API Key واقعی کار می‌کند و Merchant ID آن UUID دلخواه است.
        self.merchant_id = str(getattr(settings, 'ZARINPAL_MERCHANT_ID', '') or '').strip()
        self.base_url = (
            ZARINPAL_SANDBOX_BASE_URL
            if getattr(settings, 'ZARINPAL_SANDBOX', True)
            else ZARINPAL_PRODUCTION_BASE_URL
        )

    def _post(self, path, payload):
        try:
            response = requests.post(
                f'{self.base_url}{path}',
                json=payload,
                timeout=(3, 10),
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ValueError('ارتباط با درگاه زرین‌پال ناموفق بود.') from exc
        if not isinstance(data, dict):
            raise ValueError('پاسخ نامعتبر از درگاه زرین‌پال دریافت شد.')
        return data

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        if not self.merchant_id:
            raise ValueError('ZARINPAL_MERCHANT_ID تنظیم نشده است.')

        # قیمت‌های فروشگاه تومان هستند؛ API زرین‌پال مبلغ را ریال می‌خواهد.
        amount_rials = int(order.total) * 10
        metadata = {
            'mobile': order.phone_number,
            'order_id': order.order_number,
        }
        if order.email:
            metadata['email'] = order.email

        payload = {
            'merchant_id': self.merchant_id,
            'amount': amount_rials,
            'callback_url': callback_url,
            'description': f'پرداخت سفارش {order.order_number} - فروشگاه آتلار',
            'metadata': metadata,
        }
        data = self._post('/pg/v4/payment/request.json', payload)
        result = data.get('data') or {}
        code = result.get('code')
        authority = str(result.get('authority') or '').strip()
        if str(code) != '100' or not authority:
            errors = data.get('errors') or result.get('message') or 'خطای نامشخص'
            raise ValueError(f'درخواست پرداخت زرین‌پال رد شد: {str(errors)[:200]}')

        return PaymentRequestResult(
            redirect_url=f'{self.base_url}/pg/StartPay/{authority}',
            token=authority,
        )

    def verify_payment(self, request, expected_amount=None) -> PaymentVerifyResult:
        authority = (request.GET.get('Authority') or request.POST.get('Authority') or '').strip()
        status = (request.GET.get('Status') or request.POST.get('Status') or '').strip().upper()
        if not authority:
            return PaymentVerifyResult(success=False, message='شناسه پرداخت یافت نشد.')
        if not authority.isalnum():
            return PaymentVerifyResult(success=False, message='شناسه پرداخت نامعتبر است.')
        if status and status != 'OK':
            return PaymentVerifyResult(
                success=False,
                message='پرداخت توسط کاربر لغو یا ناموفق بود.',
                raw_response={'status': status[:32]},
            )
        if not self.merchant_id:
            return PaymentVerifyResult(success=False, message='تنظیمات درگاه کامل نیست.')
        if expected_amount is None:
            return PaymentVerifyResult(success=False, message='مبلغ تراکنش یافت نشد.')

        try:
            data = self._post('/pg/v4/payment/verify.json', {
                'merchant_id': self.merchant_id,
                'amount': int(expected_amount) * 10,
                'authority': authority,
            })
        except ValueError as exc:
            return PaymentVerifyResult(success=False, message=str(exc))
        result = data.get('data') or {}
        code = str(result.get('code') or '')
        success = code in {'100', '101'}
        amount = None
        if result.get('amount') is not None:
            try:
                amount = int(result['amount']) // 10
            except (TypeError, ValueError):
                amount = None

        return PaymentVerifyResult(
            success=success,
            ref_id=str(result.get('ref_id') or '')[:100],
            message=str(result.get('message') or data.get('errors') or '')[:500],
            raw_response=data,
            amount=amount,
        )


def get_callback_url(request) -> str:
    base = (settings.SITE_BASE_URL or '').rstrip('/')
    return f'{base}{reverse("payments:zarinpal_callback")}'
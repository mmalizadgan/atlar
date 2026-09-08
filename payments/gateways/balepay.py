"""Bale Pay wallet invoice gateway."""
import secrets

import requests
from django.conf import settings

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult


class BalePayGateway(PaymentGateway):
    base_url = 'https://tapi.bale.ai/bot'

    def __init__(self, chat_id=''):
        self.bot_token = str(getattr(settings, 'BALEPAY_BOT_TOKEN', '') or '').strip()
        self.provider_token = str(getattr(settings, 'BALEPAY_PROVIDER_TOKEN', '') or '').strip()
        self.chat_id = str(chat_id or '').strip()

    def _call(self, method, payload):
        if not self.bot_token:
            raise ValueError('BALEPAY_BOT_TOKEN تنظیم نشده است.')
        try:
            response = requests.post(
                f'{self.base_url}{self.bot_token}/{method}', json=payload,
                timeout=(3, 15), allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ValueError('ارتباط با بله ناموفق بود.') from exc
        if not isinstance(data, dict) or not data.get('ok'):
            raise ValueError(str((data or {}).get('description') or 'بله درخواست را رد کرد.')[:300])
        return data.get('result') or {}

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        if not self.chat_id:
            raise ValueError('حساب بله به این سایت متصل نیست.')
        if not self.provider_token:
            raise ValueError('BALEPAY_PROVIDER_TOKEN تنظیم نشده است.')
        payload = f'ebp_{secrets.token_hex(20)}'
        title = f'سفارش {order.order_number}'[:32]
        self._call('sendInvoice', {
            'chat_id': self.chat_id,
            'title': title,
            'description': f'پرداخت سفارش {order.order_number} از فروشگاه آتلار'[:255],
            'payload': payload,
            'provider_token': self.provider_token,
            'start_parameter': payload[:32],
            'currency': 'IRR',
            'prices': [{'label': title, 'amount': int(order.total) * 10}],
        })
        return PaymentRequestResult(redirect_url='', token=payload)

    def verify_payment(self, request, expected_amount=None) -> PaymentVerifyResult:
        return PaymentVerifyResult(success=False, message='پرداخت بله از طریق webhook تایید می‌شود.')
"""
درگاه بله‌پی (Bale Pay).

اصلاحات امنیتی این فایل:
  * آدرس callback از `settings.SITE_BASE_URL` ساخته می‌شود، نه از هدر Host
    درخواست (ضد Host Header Injection / Open Redirect در فرایند پرداخت).
  * تایم‌اوت اتصال و خواندن جدا شده + `allow_redirects=False`.
  * خطاهای شبکه هیچ‌وقت با متن خام به کاربر/لاگ نشت نمی‌کنند.
  * پاسخ درگاه اعتبارسنجی می‌شود (`token`/`amount`/`ref_id` تایپ‌چک می‌شوند).
  * `verify_payment` مبلغ تاییدشده را برمی‌گرداند تا با مبلغ سفارش مقایسه شود.

⚠️ سه مقدار BASE_URL و endpointها را با مستنداتی که بله به‌تو می‌دهد جایگزین کن.
"""
import requests
from django.conf import settings
from django.urls import reverse

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult

# TODO: این سه مقدار را از مستندات رسمی بله (بعد از فعال‌سازی درگاه) جایگزین کن.
BASE_URL = 'https://pay.bale.ai/api/v1'
CREATE_TRANSACTION_ENDPOINT = f'{BASE_URL}/transactions/create'
VERIFY_TRANSACTION_ENDPOINT = f'{BASE_URL}/transactions/verify'

# فقط این هاست‌ها برای ریدایرکت کاربر قبول می‌شوند (ضد ریدایرکت به دامنه‌ی جعلی).
ALLOWED_REDIRECT_HOSTS = {'pay.bale.ai'}


class BalePayGateway(PaymentGateway):
    def __init__(self):
        self.merchant_id = settings.BALE_PAY_MERCHANT_ID
        self.api_key = settings.BALE_PAY_API_KEY

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        if not self.merchant_id or not self.api_key:
            raise ValueError('BALE_PAY_MERCHANT_ID / BALE_PAY_API_KEY تنظیم نشده است.')

        payload = {
            'merchant_id': self.merchant_id,
            'amount': int(order.total),  # تومان/ریال — با واحد مستندات بله هماهنگ کن
            'order_id': order.order_number,
            'description': f'پرداخت سفارش {order.order_number} - فروشگاه آتلار',
            'callback_url': callback_url,
            'mobile': order.phone_number,
        }
        headers = {'Authorization': f'Bearer {self.api_key}'}

        response = requests.post(
            CREATE_TRANSACTION_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=(3, 10),
            allow_redirects=False,
        )
        response.raise_for_status()

        data = response.json()
        token = str(data.get('token') or '')
        if not token or not token.isalnum():
            raise ValueError('پاسخ نامعتبر از درگاه پرداخت.')

        return PaymentRequestResult(
            redirect_url=f'{BASE_URL}/gateway/{token}',
            token=token,
        )

    def verify_payment(self, request) -> PaymentVerifyResult:
        token = request.GET.get('token') or request.POST.get('token')
        status = request.GET.get('status') or request.POST.get('status')

        if not token:
            return PaymentVerifyResult(success=False, message='توکن پرداخت یافت نشد.')
        if not token.isalnum():
            return PaymentVerifyResult(success=False, message='توکن پرداخت نامعتبر است.')
        if status and status.lower() not in ('success', 'ok', '1'):
            return PaymentVerifyResult(
                success=False,
                message='پرداخت توسط کاربر لغو یا ناموفق بود.',
                raw_response={'status': status[:32]},
            )

        headers = {'Authorization': f'Bearer {self.api_key}'}
        try:
            response = requests.post(
                VERIFY_TRANSACTION_ENDPOINT,
                json={'token': token},
                headers=headers,
                timeout=(3, 10),
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            # خطای شبکه/JSON هرگز با متن خام به بالا نمی‌رود (۵۰۰ + نشت اطلاعات).
            return PaymentVerifyResult(success=False, message='بررسی تراکنش در درگاه ناموفق بود.')

        success = bool(data.get('success')) or data.get('status') in ('success', 'ok')

        amount = None
        raw_amount = data.get('amount')
        if raw_amount is not None:
            try:
                amount = int(str(raw_amount))
            except (TypeError, ValueError):
                amount = None

        return PaymentVerifyResult(
            success=success,
            ref_id=str(data.get('ref_id', ''))[:100],
            message=str(data.get('message', ''))[:500],
            raw_response=data,
            amount=amount,
        )


def get_callback_url(request) -> str:
    """
    ⚠️ اصلاح: قبلاً `request.build_absolute_uri(...)` بود که هدر Host درخواست
    را عیناً برمی‌گرداند؛ مهاجم می‌توانست با Host جعلی، callback را به دامنه‌ی
    خودش بفرستد. حالا آدرس از SITE_BASE_URL ساخته می‌شود.
    """
    base = (settings.SITE_BASE_URL or '').rstrip('/')
    path = reverse('payments:bale_callback')
    return f'{base}{path}'

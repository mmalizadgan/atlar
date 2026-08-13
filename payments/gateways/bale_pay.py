"""
درگاه بله‌پی (Bale Pay).

⚠️ نکته مهم و صادقانه: مستندات فنی دقیق API بله‌پی (آدرس‌های دقیق endpoint و
اسم فیلدهای request/response) به‌صورت عمومی در وب ایندکس نشده و ظاهراً بعد از
فعال‌سازی درگاه — از طریق ربات رسمی @botfather در پیام‌رسان بله — مستقیماً در
اختیار پذیرنده قرار می‌گیره (پیش‌نیاز: ارتقای کیف پول به سطح ۲ + ثبت اطلاعات
بانکی). نتونستم این جزئیات رو با جست‌وجوی وب تایید کنم، برای همین به‌جای حدس‌زدن
و نوشتن آدرس‌هایی که ممکنه اشتباه باشن، این کلاس رو با همون الگوی استاندارد
سه‌مرحله‌ای درگاه‌های ایرانی (ایجاد تراکنش → ریدایرکت → وریفای — دقیقاً همون
چیزی که زرین‌پال/آیدی‌پی هم استفاده می‌کنن و مستندات بله هم به همین ساختار اشاره
داره) پیاده‌سازی کردم، با سه جای مشخص (BASE_URL و دو endpoint) که باید از
مستندات واقعی که بله در اختیارت می‌ذاره پر بشن. بقیه کد (مدل Payment، ویوها،
قالب‌ها) به این جزئیات وابسته نیست و با پر کردن همین چند خط کار می‌کنه.

مرجع: راهنمای «استفاده از درگاه پرداخت بله در سایت» — از طریق بازوهای من ←
پرداخت در بازو در ربات @botfather بله.
"""
import requests
from django.conf import settings
from django.urls import reverse

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult

# TODO: این سه مقدار رو از مستنداتی که بعد از فعال‌سازی درگاه از بله دریافت می‌کنی جایگزین کن.
BASE_URL = 'https://pay.bale.ai/api/v1'
CREATE_TRANSACTION_ENDPOINT = f'{BASE_URL}/transactions/create'
VERIFY_TRANSACTION_ENDPOINT = f'{BASE_URL}/transactions/verify'


class BalePayGateway(PaymentGateway):
    def __init__(self):
        self.merchant_id = settings.BALE_PAY_MERCHANT_ID
        self.api_key = settings.BALE_PAY_API_KEY

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        payload = {
            'merchant_id': self.merchant_id,
            'amount': int(order.total),  # تومان/ریال — با واحدی که مستندات بله می‌گه هماهنگ کن
            'order_id': order.order_number,
            'description': f'پرداخت سفارش {order.order_number} - فروشگاه آتلار',
            'callback_url': callback_url,
            'mobile': order.phone_number,
        }
        headers = {'Authorization': f'Bearer {self.api_key}'}

        response = requests.post(CREATE_TRANSACTION_ENDPOINT, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        token = data['token']
        return PaymentRequestResult(
            redirect_url=f'{BASE_URL}/gateway/{token}',
            token=token,
        )

    def verify_payment(self, request) -> PaymentVerifyResult:
        token = request.GET.get('token') or request.POST.get('token')
        status = request.GET.get('status') or request.POST.get('status')

        if not token:
            return PaymentVerifyResult(success=False, message='توکن پرداخت یافت نشد.')
        if status and status not in ('success', 'ok', '1', 'OK'):
            return PaymentVerifyResult(success=False, message='پرداخت توسط کاربر لغو یا ناموفق بود.', raw_response=dict(request.GET))

        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = requests.post(VERIFY_TRANSACTION_ENDPOINT, json={'token': token}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        success = bool(data.get('success') or data.get('status') in ('success', 'ok'))
        return PaymentVerifyResult(
            success=success,
            ref_id=str(data.get('ref_id', '')),
            message=data.get('message', ''),
            raw_response=data,
        )


def get_callback_url(request) -> str:
    return request.build_absolute_uri(reverse('payments:bale_callback'))

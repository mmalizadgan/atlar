from dataclasses import dataclass


@dataclass
class PaymentRequestResult:
    redirect_url: str
    token: str


@dataclass
class PaymentVerifyResult:
    success: bool
    ref_id: str = ''
    message: str = ''
    raw_response: dict | None = None


class PaymentGateway:
    """
    اینترفیس مشترک درگاه‌های پرداخت. هر درگاه (بله‌پی، زرین‌پال و ...) این کلاس رو
    پیاده‌سازی می‌کنه، تا views.py و بقیه‌ی کد به هیچ درگاه خاصی وابسته نباشه —
    عوض کردن درگاه یعنی فقط عوض کردن همین یک کلاس.
    """

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        raise NotImplementedError

    def verify_payment(self, request) -> PaymentVerifyResult:
        raise NotImplementedError

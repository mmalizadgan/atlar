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
    # ⚠️ جدید: مبلغ تاییدشده توسط درگاه — در callback با مبلغ سفارش مقایسه می‌شود.
    amount: int | None = None

from abc import ABC, abstractmethod
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
    amount: int | None = None


class PaymentGateway(ABC):
    """رابط مشترک درگاه‌های پرداخت."""

    @abstractmethod
    def request_payment(self, order, callback_url: str) -> PaymentRequestResult: ...

    @abstractmethod
    def verify_payment(self, request, expected_amount=None) -> PaymentVerifyResult: ...

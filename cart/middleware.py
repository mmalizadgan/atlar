from django.utils.functional import SimpleLazyObject

from .models import Cart


def _resolve_cart(request):
    """
    فقط سبدی که از قبل وجود داره رو می‌خونه؛ چیزی نمی‌سازه.
    ساختن Cart (و سشن) فقط موقع اولین "افزودن به سبد" اتفاق می‌افته
    (در cart/views.py) تا برای بازدیدکننده‌هایی که چیزی نمی‌خرن رکورد اضافه در دیتابیس نسازیم.
    """
    session_key = request.session.session_key
    if not session_key:
        return None
    return Cart.objects.filter(session_key=session_key).first()


class CartMiddleware:
    """request.cart رو به‌صورت lazy وصل می‌کنه (فقط وقتی واقعاً استفاده بشه، کوئری می‌زنه)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cart = SimpleLazyObject(lambda: _resolve_cart(request))
        return self.get_response(request)

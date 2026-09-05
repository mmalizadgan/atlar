"""
میدل‌ور هدرهای امنیتی — این فایل **جدید** است و در config/settings.py اضافه شده.

چرا: Django به‌صورت پیش‌فرض CSP و Permissions-Policy نمی‌فرستد. بدون CSP، یک
XSS کوچک (حتی در یک وابستگی فرانت مثل Bootstrap) می‌تواند اسکریپت خارجی
بارگذاری کند و session کاربر را بدزدد.

نکته: 'unsafe-inline' برای script لازم است چون در قالب‌ها اسکریپت inline داریم.
برای حذفش، اسکریپت‌ها را به فایل static منتقل کن و از nonce استفاده کن.
"""

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', CSP_POLICY)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=(), payment=()',
        )
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        return response

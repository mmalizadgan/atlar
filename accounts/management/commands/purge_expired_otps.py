"""
پاک‌سازی کدهای یک‌بارمصرف منقضی — جلوی بی‌نهایت بزرگ‌شدن جدول `accounts_otp`
را می‌گیرد (جدولی که هر بات می‌تواند با درخواست پی‌درپی کد، پرش کند).

اجرا:
    python manage.py purge_expired_otps            # حذف کدهای منقضی‌شده
    python manage.py purge_expired_otps --days 3   # نگه‌داشتن ۳ روز اخیر

پیشنهاد: در cron هر ساعت:
    0 * * * * cd /srv/atlar && python manage.py purge_expired_otps --days 1
"""
from django.core.management.base import BaseCommand

from accounts.services.otp import purge_expired_otps


class Command(BaseCommand):
    help = 'کدهای OTP منقضی‌شده را از دیتابیس حذف می‌کند.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=1,
            help='رکوردهای منقضی‌شده‌ی جدیدتر از این تعداد روز نگه داشته می‌شوند (پیش‌فرض ۱).',
        )

    def handle(self, *args, **options):
        deleted = purge_expired_otps(keep_days=max(0, options['days']))
        self.stdout.write(self.style.SUCCESS(f'{deleted} رکورد OTP منقضی حذف شد.'))

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse


class Command(BaseCommand):
    help = 'Register the Bale bot webhook for Bale Pay.'

    def handle(self, *args, **options):
        token = str(getattr(settings, 'BALEPAY_BOT_TOKEN', '') or '').strip()
        secret = str(getattr(settings, 'BALEPAY_WEBHOOK_SECRET', '') or '').strip()
        base_url = str(getattr(settings, 'SITE_BASE_URL', '') or '').rstrip('/')
        if not token or not secret or not base_url:
            raise CommandError('BALEPAY_BOT_TOKEN، BALEPAY_WEBHOOK_SECRET و SITE_BASE_URL الزامی هستند.')

        webhook_url = f'{base_url}{reverse("payments:balepay_webhook", kwargs={"secret": secret})}'
        try:
            response = requests.post(
                f'https://tapi.bale.ai/bot{token}/setWebhook',
                json={'url': webhook_url}, timeout=(3, 15),
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise CommandError(f'ثبت webhook در بله ناموفق بود: {exc}') from exc
        if not isinstance(result, dict) or not result.get('ok'):
            raise CommandError(str((result or {}).get('description') or 'بله ثبت webhook را رد کرد.'))
        self.stdout.write(self.style.SUCCESS(f'Webhook ثبت شد: {webhook_url}'))

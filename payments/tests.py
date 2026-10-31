from unittest.mock import patch

from django.test import TestCase 
from django.urls import reverse 
 
from accounts.models import User 
from orders.models import Order 
 
from .models import Payment


class PendingOrderPaymentRetryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='09123456789')
        self.order = Order.objects.create(
            user=self.user,
            full_name='خریدار آزمایشی',
            phone_number='09123456789',
            address_line='نشانی آزمایشی',
            city='تهران',
            postal_code='1234567890',
            subtotal=100000,
            total=100000,
        )
        self.client.force_login(self.user)

    @patch(
        'payments.views.BalePayGateway.request_payment',
        side_effect=ValueError('خطای موقت درگاه'),
    )
    def test_failed_bale_payment_can_be_retried_through_bale(self, request_payment):
        session = self.client.session
        session['balepay_chat_id'] = '12345'
        session.save()

        response = self.client.get(reverse(
            'payments:initiate_with_gateway',
            kwargs={'order_number': self.order.order_number, 'gateway': 'balepay'},
        ))

        self.assertRedirects(response, reverse(
            'orders:detail', kwargs={'order_number': self.order.order_number},
        ))
        request_payment.assert_called_once()
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

        detail_response = self.client.get(
            reverse('orders:detail', kwargs={'order_number': self.order.order_number})
        )
        retry_url = reverse(
            'payments:initiate_with_gateway',
            kwargs={'order_number': self.order.order_number, 'gateway': 'balepay'},
        )
        self.assertContains(detail_response, f'href="{retry_url}"')

    def test_pending_order_without_payment_defaults_to_zarinpal(self):
        response = self.client.get(
            reverse('orders:detail', kwargs={'order_number': self.order.order_number})
        )
        retry_url = reverse(
            'payments:initiate_with_gateway',
            kwargs={'order_number': self.order.order_number, 'gateway': 'zarinpal'},
        )
        self.assertContains(response, f'href="{retry_url}"')

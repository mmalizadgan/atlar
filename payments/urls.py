from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/<str:order_number>/<str:gateway>/', views.initiate_payment_view, name='initiate_with_gateway'),
    path('initiate/<str:order_number>/', views.initiate_payment_view, name='initiate'),
    path('connect/<str:order_number>/<str:gateway>/', views.balepay_connect_view, name='connect'),
    path('connect/<str:order_number>/', views.balepay_connect_view, {'gateway': 'balepay'}, name='connect_legacy'),
    path('connection-status/', views.balepay_connection_status_view, name='connection_status'),
    path('status/<str:order_number>/', views.balepay_payment_status_view, name='status'),
    path('balepay/webhook/<str:secret>/', views.balepay_webhook_view, name='balepay_webhook'),
    path('zarinpal/callback/', views.zarinpal_callback_view, name='zarinpal_callback'),
]

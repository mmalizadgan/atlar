from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('initiate/<str:order_number>/', views.initiate_payment_view, name='initiate'),
    path('bale/callback/', views.bale_callback_view, name='bale_callback'),
]

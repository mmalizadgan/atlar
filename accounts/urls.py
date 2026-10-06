from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_request_view, name='login'),
    path('login/verify/', views.login_verify_view, name='verify'),
    path('login/resend/', views.resend_otp_view, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/address/add/', views.address_create_view, name='address_add'),
    path('profile/address/<int:pk>/edit/', views.address_edit_view, name='address_edit'),
    path('profile/address/<int:pk>/delete/', views.address_delete_view, name='address_delete'),
    path('profile/address/<int:pk>/default/', views.address_set_default_view, name='address_set_default'),
]

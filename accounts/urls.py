from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_request_view, name='login'),
    path('login/verify/', views.login_verify_view, name='verify'),
    path('login/resend/', views.resend_otp_view, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
]

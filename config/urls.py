from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.templatetags.static import static as static_url
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = 'مدیریت فروشگاه آتلار'
admin.site.site_title = 'آتلار'
admin.site.index_title = 'پنل مدیریت'

urlpatterns = [
    # ⚠️ اصلاح: مسیر پنل ادمین از ADMIN_URL در .env خوانده می‌شود تا
    # اسکنرهای خودکاری که /admin/ را تست می‌کنند بی‌نتیجه بمانند.
    path(settings.ADMIN_URL, admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url=static_url('favicon.ico'), permanent=True)),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('payments/', include('payments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

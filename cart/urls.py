from django.urls import path

from products.converters import UnicodeSlugConverter  # noqa: F401 — importing registers the 'uslug' converter

from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail_view, name='detail'),
    path('add/<uslug:slug>/', views.add_to_cart_view, name='add'),
    path('update/<int:item_id>/', views.update_cart_item_view, name='update'),
    path('remove/<int:item_id>/', views.remove_from_cart_view, name='remove'),
]

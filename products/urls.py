from django.urls import path

from . import views
from .converters import UnicodeSlugConverter  # noqa: F401 — importing registers the 'uslug' converter

app_name = 'products'

urlpatterns = [
    path('', views.fabric_list_view, name='fabric_list'),
    path('category/<uslug:category_slug>/', views.fabric_list_view, name='category_detail'),
    path('<uslug:slug>/', views.fabric_detail_view, name='fabric_detail'),
]

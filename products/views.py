from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from core.models import SiteSettings

from .models import Category, Fabric

PAGE_SIZE = 12


def _active_categories():
    categories = cache.get('active_categories')
    if categories is None:
        categories = list(Category.objects.filter(is_active=True))
        cache.set('active_categories', categories, 60 * 15)
    return categories


def fabric_list_view(request, category_slug=None):
    fabrics = Fabric.objects.active().with_gallery()

    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug, is_active=True)
        fabrics = fabrics.filter(category=current_category)

    query = request.GET.get('q', '').strip()
    if query:
        fabrics = fabrics.filter(
            Q(name__icontains=query) | Q(description__icontains=query) |
            Q(material__icontains=query) | Q(color_variants__color_name__icontains=query)
        ).distinct()

    color = request.GET.get('color', '').strip()
    if color:
        fabrics = fabrics.filter(color_variants__color_name__icontains=color).distinct()

    sort = request.GET.get('sort', 'newest')
    sort_map = {
        'newest': '-created_at',
        'price_asc': 'price_per_meter',
        'price_desc': '-price_per_meter',
        'name': 'name',
    }
    fabrics = fabrics.order_by(sort_map.get(sort, '-created_at'))

    paginator = Paginator(fabrics, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'fabrics': page_obj.object_list,
        'categories': _active_categories(),
        'current_category': current_category,
        'query': query,
        'sort': sort,
    }
    return render(request, 'products/fabric_list.html', context)


def fabric_detail_view(request, slug):
    fabric = get_object_or_404(
        Fabric.objects.select_related('category').prefetch_related('color_variants', 'color_variants__images'),
        slug=slug, is_active=True,
    )
    related_fabrics = (
        Fabric.objects.active()
        .filter(category=fabric.category)
        .exclude(pk=fabric.pk)
        .select_related('category')
        .prefetch_related('color_variants')[:4]
    )
    return render(request, 'products/fabric_detail.html', {
        'fabric': fabric,
        'variants': fabric.active_variants,
        'related_fabrics': related_fabrics,
        'fabric_width_cm': SiteSettings.load().default_fabric_width_cm,
    })

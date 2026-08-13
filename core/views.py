from django.shortcuts import render

from products.models import Category, Fabric


def home_view(request):
    featured = (
        Fabric.objects.active().with_gallery().filter(is_featured=True)[:8]
    )
    if not featured:
        featured = Fabric.objects.active().with_gallery().order_by('-created_at')[:8]

    categories = Category.objects.filter(is_active=True)[:6]

    return render(request, 'core/home.html', {
        'featured_fabrics': featured,
        'categories': categories,
    })


def about_view(request):
    return render(request, 'core/about.html')

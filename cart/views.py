from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Fabric, FabricColorVariant

from .models import Cart, CartItem

# سقف مجاز هر آیتم سبد (ضد مقدارهای عجیب مثل 1E+3 یا 99999.9)
MAX_METERS_PER_ITEM = Decimal('500')


def _get_or_create_cart(request):
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    request.cart = cart
    return cart


def _parse_quantity(raw_value, default=Decimal('1')):
    """
    ⚠️ اصلاح: قبلاً `Decimal('1E+3')` (نماد علمی) پذیرفته می‌شد و مقدار ۱۰۰۰
    به سبد می‌رفت. حالا: فقط عدد اعشاری ساده، بدون نماد علمی و با سقف مشخص.
    """
    if raw_value is None:
        return default
    try:
        value = Decimal(str(raw_value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        return default
    if not value.is_finite():
        return default
    value = value.quantize(Decimal('0.1'))
    if value <= 0:
        return default
    if value > MAX_METERS_PER_ITEM:
        return MAX_METERS_PER_ITEM
    return value


def cart_detail_view(request):
    cart = request.cart
    items = cart.items_qs if cart else []
    return render(request, 'cart/cart_detail.html', {'cart': cart, 'items': items})


@require_POST
def add_to_cart_view(request, slug):
    fabric = get_object_or_404(Fabric, slug=slug, is_active=True)

    variant_id = request.POST.get('variant_id')
    if variant_id and variant_id.isdigit():
        variant = get_object_or_404(FabricColorVariant, pk=variant_id, fabric=fabric, is_active=True)
    else:
        variant = fabric.default_variant
    if variant is None:
        messages.error(request, f'برای «{fabric.name}» رنگ‌بندی فعالی ثبت نشده.')
        return redirect(fabric.get_absolute_url())

    quantity = _parse_quantity(request.POST.get('quantity_meters'), default=fabric.min_order_meters)
    label = f'{fabric.name} — {variant.color_name}'

    if quantity < fabric.min_order_meters:
        messages.error(request, f'حداقل سفارش برای «{label}» {fabric.min_order_meters} متره.')
        return redirect(fabric.get_absolute_url())

    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant, defaults={'quantity_meters': quantity}
    )
    if not created:
        quantity = item.quantity_meters + quantity

    if quantity > variant.stock_meters:
        messages.error(request, f'موجودی «{label}» فقط {variant.stock_meters} متره.')
        if created:
            item.delete()
        return redirect(fabric.get_absolute_url())

    item.quantity_meters = quantity
    item.save(update_fields=['quantity_meters'])
    messages.success(request, f'«{label}» به سبد خرید اضافه شد.')
    return redirect(fabric.get_absolute_url())


@require_POST
def update_cart_item_view(request, item_id):
    cart = request.cart
    # ⚠️ اصلاح: کوئری روی pk، کاربر/سبد فیلتر می‌شود → دستکاری سبد دیگران ممکن نیست.
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    quantity = _parse_quantity(request.POST.get('quantity_meters'), default=item.quantity_meters)
    fabric = item.variant.fabric

    if quantity < fabric.min_order_meters:
        messages.error(request, f'حداقل سفارش {fabric.min_order_meters} متره.')
    elif quantity > item.variant.stock_meters:
        messages.error(request, f'موجودی فقط {item.variant.stock_meters} متره.')
    else:
        item.quantity_meters = quantity
        item.save(update_fields=['quantity_meters'])
        messages.success(request, 'سبد خرید به‌روزرسانی شد.')
    return redirect('cart:detail')


@require_POST
def remove_from_cart_view(request, item_id):
    cart = request.cart
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.info(request, 'آیتم از سبد حذف شد.')
    return redirect('cart:detail')

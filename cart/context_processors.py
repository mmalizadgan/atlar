from decimal import Decimal


def cart(request):
    current_cart = getattr(request, 'cart', None)
    if not current_cart:
        return {
            'cart_item_count': 0,
            'cart_subtotal': 0,
            'cart_total_meters': 0,
            'free_shipping_remaining_meters': 50,
            'free_shipping_progress_percent': 0,
        }

    total_meters = current_cart.total_items or Decimal('0')
    threshold_meters = Decimal('50')
    remaining_meters = max(Decimal('0'), threshold_meters - total_meters)
    progress = min(Decimal('100'), (total_meters / threshold_meters) * Decimal('100')) if threshold_meters else Decimal('0')

    return {
        'cart_item_count': current_cart.items.count(),
        'cart_subtotal': current_cart.subtotal,
        'cart_total_meters': total_meters,
        'free_shipping_remaining_meters': remaining_meters,
        'free_shipping_progress_percent': progress,
    }

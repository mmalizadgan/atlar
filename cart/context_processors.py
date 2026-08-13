def cart(request):
    current_cart = getattr(request, 'cart', None)
    if not current_cart:
        return {'cart_item_count': 0, 'cart_subtotal': 0}
    return {
        'cart_item_count': current_cart.items.count(),
        'cart_subtotal': current_cart.subtotal,
    }

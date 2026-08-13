from django import template
import locale

register = template.Library()


@register.filter
def format_price(value):
    """فرمت قیمت با کاما و کلمه تومان"""
    try:
        price = int(float(value))
        return f"{price:,}"
    except (ValueError, TypeError):
        return value

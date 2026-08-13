from django.urls import register_converter


class UnicodeSlugConverter:
    """
    مبدل مسیر برای اسلاگ‌های یونیکد (فارسی). کانورتر پیش‌فرض <slug:...> جنگو
    فقط ASCII قبول می‌کنه؛ چون Category/Fabric.slug با allow_unicode=True
    ساخته می‌شن (مثلاً «مخمل»)، باید از همین کانورتر استفاده کنیم.
    """
    regex = r'[-\w]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


# ثبت در همین‌جا (نه در هر urls.py) تا صرف‌نظر از ترتیب import، دقیقاً یک‌بار ثبت بشه.
register_converter(UnicodeSlugConverter, 'uslug')

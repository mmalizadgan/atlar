from django.core.management.base import BaseCommand

from products.models import Category, Fabric, FabricColorVariant


class Command(BaseCommand):
    help = 'چند دسته‌بندی، کالیته و رنگ‌بندی نمونه برای تست/نمایش اولیه سایت می‌سازد.'

    def handle(self, *args, **options):
        categories_data = [
            ('مخمل', 'پارچه‌های مخمل نرم و مقاوم برای مبلمان کلاسیک و مدرن'),
            ('چرم مصنوعی', 'چرم مصنوعی باکیفیت، مقاوم در برابر خش و سایش'),
            ('کتان', 'پارچه‌های کتان طبیعی و خنک برای فضاهای روشن'),
            ('طرح‌دار هندسی', 'طرح‌های هندسی مدرن برای دکوراسیون امروزی'),
        ]
        categories = {}
        for i, (name, desc) in enumerate(categories_data):
            cat, _ = Category.objects.get_or_create(name=name, defaults={'description': desc, 'order': i})
            categories[name] = cat

        # هر ردیف یک «کالیته»؛ colors: [(نام‌رنگ, کد‌هگز, موجودی), ...]
        fabrics_data = [
            (
                'مخمل سلطنتی', 'مخمل', 'ساده', '۱۰۰٪ پلی‌استر', 1250000, True, True,
                [('زرشکی', '#7a1f2b', 45), ('طوسی', '#8a8f94', 38), ('سرمه‌ای', '#1c3350', 20)],
            ),
            (
                'چرم مصنوعی مات', 'چرم مصنوعی', 'ساده', 'PU روکش‌دار', 1450000, True, False,
                [('مشکی', '#1a1a1a', 30), ('کرم', '#e8dcc8', 26), ('قهوه‌ای', '#5b3a29', 0)],
            ),
            (
                'کتان طبیعی', 'کتان', 'ساده', '۱۰۰٪ کتان', 890000, True, True,
                [('خاکی', '#a68a64', 60), ('سفید', '#f2efe9', 15)],
            ),
            (
                'هندسی مدرن', 'طرح‌دار هندسی', 'هندسی', 'پلی‌استر ترکیبی', 1120000, True, True,
                [('طلایی/سرمه‌ای', '#c69a4e', 20), ('طوسی/کرم', '#b9b2a3', 18)],
            ),
        ]
        for name, cat_name, pattern, material, price, featured, washable, colors in fabrics_data:
            fabric, _ = Fabric.objects.get_or_create(
                name=name,
                defaults=dict(
                    category=categories[cat_name], pattern=pattern, material=material, price_per_meter=price,
                    is_featured=featured, is_washable=washable,
                    abrasion_rating=35000, min_order_meters=1,
                    description=f'{name} با دوام بالا، مناسب مبلمان خانگی و اداری — در چند رنگ‌بندی موجوده.',
                ),
            )
            for order, (color_name, color_hex, stock) in enumerate(colors):
                FabricColorVariant.objects.get_or_create(
                    fabric=fabric, color_name=color_name,
                    defaults=dict(color_hex=color_hex, stock_meters=stock, order=order),
                )

        self.stdout.write(self.style.SUCCESS(
            f'{Category.objects.count()} دسته‌بندی، {Fabric.objects.count()} کالیته و '
            f'{FabricColorVariant.objects.count()} رنگ‌بندی آماده شد.'
        ))

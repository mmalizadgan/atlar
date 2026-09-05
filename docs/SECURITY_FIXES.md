# گزارش امنیتی و راهنمای اعمال اصلاحات — آتلار

این سند خلاصه‌ی کامل ایرادات پیدا‌شده و فایل‌هایی است که باید جایگزین شوند.
**هر فایلی که در این جدول آمده، نسخه‌ی اصلاح‌شده‌اش در همین مخزن آماده است** —
فقط محتوای فایل قدیمی را با فایل جدید جایگزین کن.

## ۱) فایل‌های تغییر‌یافته / اضافه‌شده

| # | فایل | وضعیت | توضیح |
|---|------|-------|-------|
| ۱ | `accounts/models.py` | ✏️ جایگزین | `secrets` به‌جای `random`، حذف فیلد `code`، افزودن `code_hash`/`session_key`/`verified_at` |
| ۲ | `accounts/services/otp.py` | ➕ جدید | هسته‌ی امن OTP: هش، قفل، محدودیت نرخ، session binding |
| ۳ | `accounts/services/__init__.py` | ✏️ جایگزین | export‌های سرویس OTP |
| ۴ | `accounts/services/sms.py` | ✏️ جایگزین | حذف `print()`، جلوگیری از نشت API key، allow-list سرویس‌ها |
| ۵ | `accounts/backends.py` | ✏️ جایگزین | مقایسه‌ی constant-time روی هش، عبور خطاها به ویو |
| ۶ | `accounts/views.py` | ✏️ جایگزین | قفل/نرخ، `next` امن، شماره‌ی ماسک‌شده |
| ۷ | `accounts/forms.py` | ✏️ جایگزین | نرمال‌سازی ارقام فارسی، فقط رقم در کد OTP |
| ۸ | `accounts/admin.py` | ✏️ جایگزین | حذف نمایش کد OTP از پنل ادمین، رکورد فقط‌خواندنی |
| ۹ | `accounts/migrations/0003_otp_security.py` | ➕ جدید | مایگریشن تغییرات مدل OTP |
| ۱۰ | `accounts/management/commands/purge_expired_otps.py` | ➕ جدید | پاک‌سازی کدهای منقضی (cron) |
| ۱۱ | `accounts/templates/accounts/login_verify.html` | ✏️ جایگزین | شماره‌ی ماسک‌شده + نمایش قفل |
| ۱۲ | `accounts/tests.py` | ✏️ جایگزین | تست‌های امنیتی (brute force، قفل، SMS bombing) |
| ۱۳ | `config/settings.py` | ✏️ جایگزین | هدرهای امنیتی، OTP سخت‌تر، لاگ، ADMIN_URL |
| ۱۴ | `config/middleware.py` | ➕ جدید | CSP و Permissions-Policy |
| ۱۵ | `config/urls.py` | ✏️ جایگزین | مسیر ادمین از `ADMIN_URL` |
| ۱۶ | `orders/views.py` | ✏️ جایگزین | رزرو موجودی با `select_for_update`، خالی‌کردن سبد، لغو سفارش |
| ۱۷ | `orders/urls.py` | ✏️ جایگزین | مسیر `orders/<nr>/cancel/` |
| ۱۸ | `orders/models.py` | ✏️ ویرایش | تولید `order_number` مقاوم به تصادم |
| ۱۹ | `payments/views.py` | ✏️ جایگزین | callback غیرتکراری (idempotent)، بررسی مبلغ، رفع باگ `fabric_id` |
| ۲۰ | `payments/gateways/bale_pay.py` | ✏️ جایگزین | callback از `SITE_BASE_URL`، تایم‌اوت، اعتبارسنجی پاسخ |
| ۲۱ | `payments/gateways/base.py` | ✏️ جایگزین | افزودن `amount` به نتیجه‌ی verify |
| ۲۲ | `cart/views.py` | ✏️ جایگزین | سقف متراژ، رد نماد علمی، فیلتر سبد |
| ۲۳ | `.env.example` | ✏️ جایگزین | کلیدهای جدید |

## ۲) بعد از جایگزینی چه اجرا کنی؟

```bash
# ۱) مایگریشن مدل OTP
python manage.py migrate accounts

# ۲) بررسی سلامت
python manage.py check --deploy          # باید خطای SECRET_KEY/DEBUG نداشته باشد

# ۳) تست‌های امنیتی
python manage.py test accounts orders payments -v 2

# ۴) پاک‌سازی دوره‌ای (cron: هر ساعت)
python manage.py purge_expired_otps --days 1
```

## ۳) کارهایی که فقط با تنظیم `.env` درست می‌شوند

```env
DEBUG=False
SECRET_KEY=<کلید تصادفی>
ALLOWED_HOSTS=atlar.ir,www.atlar.ir
CSRF_TRUSTED_ORIGINS=https://atlar.ir
ADMIN_URL=xk92-admin/          # مسیر ادمین را عوض کن
SITE_BASE_URL=https://atlar.ir
TRUST_PROXY_HEADERS=True        # فقط اگر پشت nginx/CDN هستی
```

## ۴) مهم‌ترین ریسک باقی‌مانده (باید قبل از لانچ انجام شود)

1. **کش مشترک**: محدودیت نرخ OTP با `LocMemCache` فقط per-process است. حتماً Redis
   راه بینداز (خط کامنت‌شده در `config/settings.py`). بدون این، با چند worker gunicorn
   محدودیت‌ها ضعیف می‌شوند.
2. **پیامک واقعی**: تا وقتی `SMS_PROVIDER=console` است، کد به کاربر نمی‌رسد.
3. **نصب `django-axes`** روی پنل ادمین (برای محدودیت تلاش ورود ادمین) توصیه می‌شود.
4. **گواهی HTTPS** و تنظیم `SECURE_PROXY_SSL_HEADER` در nginx.
5. **پشتیبان‌گیری روزانه‌ی دیتابیس** + نگه‌داشتن `.env` خارج از git (الان درست است).

## ۵) پاسخ کوتاه به سؤال «OTP قابل حدس است؟»

**بله، در نسخه‌ی فعلی قابل حدس بود.** سه دلیل:

1. `random.choices` (Mersenne Twister) استفاده شده بود — یک PRNG **رمزنگارانه نیست**.
2. کد ۵ رقمی بود = فقط ۱۰۰٫۰۰۰ حالت.
3. محدودیت فقط «۵ تلاش به‌ازای هر کد» بود؛ مهاجم با گرفتن کد جدید شمارنده را صفر می‌کرد
   و چون هیچ محدودیتی روی IP یا تعداد شکست‌های انباشته نبود، می‌توانست بی‌وقفه حدس بزند
   (~۵ حدس در هر ۹۰ ثانیه ≈ ۴٫۸۰۰ حدس در روز برای یک شماره؛ و برای همه‌ی شماره‌ها موازی).

با اصلاحات انجام‌شده: کد ۶ رقمی با `secrets`، ذخیره‌ی فقط هش، مقایسه‌ی constant-time،
سوزاندن کد بعد از ۵ حدس، قفل ۱۵ دقیقه‌ای شماره بعد از ۸ شکست، سقف ۳ کد در ساعت برای هر
شماره و ۱۰ کد در ساعت برای هر IP، و ۱۵ تلاش تایید در هر ۱۵ دقیقه برای هر IP.

نتیجه: حدس موفق عملاً غیرممکن می‌شود (به‌جای ۱۰۰٫۰۰۰ حالتِ بی‌محدودیت،
۹ شکست مجاز در هر ۱۵ دقیقه با احتمال موفقیت ۹/۱٫۰۰۰٫۰۰۰ ≈ ۰٫۰۰۰۹٪).

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    سخت‌سازی مدل OTP:
      * حذف فیلد `code` (ذخیره‌ی متن خام کد = خطر بالا)
      * افزودن `code_hash` (HMAC-SHA256)
      * افزودن `session_key` (گره‌خوردن کد به نشست صادرکننده)
      * افزودن `verified_at` (ثبت زمان تایید موفق برای audit)

    بعد از اعمال این مایگریشن، کدهای قدیمی (که متن خام بودند) بی‌اعتبار
    می‌شوند و کاربران باید کد جدید بگیرند — رفتار امن و مورد انتظار.
    """

    dependencies = [
        ('accounts', '0002_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='otp',
            name='session_key',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='otp',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='otp',
            name='code_hash',
            field=models.CharField(default='', editable=False, max_length=64),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='otp',
            name='code',
        ),
        migrations.AlterField(
            model_name='otp',
            name='attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]

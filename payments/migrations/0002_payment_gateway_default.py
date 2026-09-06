from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='gateway',
            field=models.CharField(default='zarinpal', max_length=30),
        ),
    ]
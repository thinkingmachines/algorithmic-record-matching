# Generated by Django 2.0.7 on 2018-08-13 07:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_auto_20180806_0055'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='is_internal',
            field=models.BooleanField(default=False),
        ),
    ]

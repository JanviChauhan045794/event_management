# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('events', '0022_merge_20250606_1953'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='is_read',
            field=models.BooleanField(default=False),
        ),
    ] 
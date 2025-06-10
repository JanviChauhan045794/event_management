# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('events', '0017_add_notification_preferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsor',
            name='name',
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
    ] 
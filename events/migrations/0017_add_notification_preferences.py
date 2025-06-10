# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('events', '0016_add_notification_preferences'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsorprofile',
            name='notification_preferences',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Notification preferences for different types of updates'
            ),
        ),
    ] 
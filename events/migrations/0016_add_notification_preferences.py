# Generated manually

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('events', '0015_sponsorprofile_sponsortier_alter_sponsor_options_and_more'),
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
        migrations.AddField(
            model_name='sponsorprofile',
            name='display_preferences',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Display preferences for public profile'
            ),
        ),
    ] 
# Generated by Django 5.1.7 on 2025-04-22 05:20

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_registration_reminders_enabled_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('notification_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('notification_type', models.CharField(choices=[('event_created', 'New Event Created'), ('event_updated', 'Event Updated'), ('event_reminder', 'Event Reminder'), ('registration_confirmed', 'Registration Confirmed'), ('speaker_added', 'Speaker Added'), ('feedback_request', 'Feedback Request')], max_length=50)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('icon', models.CharField(default='fa-bell', max_length=50)),
                ('color', models.CharField(default='primary', max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('action_url', models.CharField(blank=True, max_length=255)),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='events.event')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('event_reminder', 'Event Reminder'),
        ('registration', 'Registration Update'),
        ('event_update', 'Event Update'),
        ('feedback', 'Feedback Request'),
        ('system', 'System Notification'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    related_event = models.ForeignKey('Event', on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    icon_class = models.CharField(max_length=50, default='fas fa-bell')  # FontAwesome icon class

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    def mark_as_read(self):
        self.is_read = True
        self.save()

    @property
    def time_since(self):
        """Returns a human-readable string of how long ago the notification was created"""
        now = timezone.now()
        diff = now - self.created_at

        if diff.days > 7:
            return self.created_at.strftime('%B %d, %Y')
        elif diff.days > 0:
            return f'{diff.days} days ago'
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f'{hours} hours ago'
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f'{minutes} minutes ago'
        else:
            return 'Just now' 
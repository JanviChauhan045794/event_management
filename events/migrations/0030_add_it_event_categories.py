from django.db import migrations

def add_event_categories(apps, schema_editor):
    EventCategory = apps.get_model('events', 'EventCategory')
    categories = [
        'Tech Conference',
        'Workshop',
        'Webinar',
        'Training Session',
        'Product Launch',
        'Developer Meetup',
        'Tech Summit',
        'AI/ML Conference',
        'Cloud Computing Event',
        'DevOps Conference',
        'Cybersecurity Symposium',
        'Data Science Workshop',
        'Blockchain Summit',
        'IoT Conference',
        'Software Architecture Summit',
        'Mobile Development Conference',
        'Web Development Workshop',
        'UX/UI Design Workshop',
        'Digital Transformation Summit',
        'IT Leadership Conference',
        'Agile/Scrum Workshop',
        'API Conference',
        'Testing & QA Conference',
        'Big Data Analytics Summit',
        'Enterprise Software Conference',
        'IT Infrastructure Event',
        'Network Security Workshop',
        'Cloud Migration Workshop',
        'Microservices Summit',
        'IT Project Management Workshop'
    ]
    
    for category_name in categories:
        EventCategory.objects.get_or_create(name=category_name)

def remove_event_categories(apps, schema_editor):
    EventCategory = apps.get_model('events', 'EventCategory')
    EventCategory.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('events', '0028_remove_notification_action_url_and_more'),
    ]

    operations = [
        migrations.RunPython(add_event_categories, remove_event_categories),
    ] 
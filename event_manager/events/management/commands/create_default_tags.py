from django.core.management.base import BaseCommand
from events.models import EventTag

class Command(BaseCommand):
    help = 'Creates default technology tags for events'

    def handle(self, *args, **kwargs):
        # Define default technology tags with descriptions
        default_tags = {
            'AI/ML': 'Artificial Intelligence and Machine Learning',
            'DevOps': 'Development Operations and Continuous Integration/Deployment',
            'Cloud Computing': 'Cloud platforms and services (AWS, Azure, GCP)',
            'Kubernetes': 'Container orchestration and cloud-native applications',
            'Java': 'Java programming language and ecosystem',
            'Python': 'Python programming language and frameworks',
            'JavaScript': 'JavaScript, TypeScript, and web development',
            'Web Development': 'Frontend and backend web technologies',
            'Mobile Development': 'iOS, Android, and cross-platform development',
            'Blockchain': 'Blockchain technology and cryptocurrencies',
            'Data Science': 'Data analysis, visualization, and statistics',
            'Big Data': 'Big data processing and analytics',
            'IoT': 'Internet of Things and embedded systems',
            'Cybersecurity': 'Information security and cyber defense',
            'UI/UX': 'User Interface and User Experience design',
            'Agile': 'Agile methodologies and project management',
            'Microservices': 'Microservices architecture and design',
            'API Development': 'API design, development, and integration',
            'Testing': 'Software testing and quality assurance',
            'Database': 'Database systems and data management',
            'Linux': 'Linux systems and administration',
            'Network': 'Computer networking and infrastructure',
            'Cloud Native': 'Cloud-native applications and practices',
            'Serverless': 'Serverless computing and architecture',
            'Docker': 'Containerization and Docker ecosystem',
        }

        # Create tags
        for name, description in default_tags.items():
            EventTag.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'is_tech': True
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully created default technology tags')) 
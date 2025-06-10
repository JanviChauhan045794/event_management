from django.core.management.base import BaseCommand
from events.models import SponsorTier


class Command(BaseCommand):
    help = 'Create default sponsor tiers'

    def handle(self, *args, **options):
        # Define default sponsor tiers
        default_tiers = [
            {
                'name': 'Platinum',
                'display_order': 1,
                'color_code': '#E5E4E2',
                'base_price': 10000.00,
                'logo_placement': 'Main stage backdrop, Website header, All marketing materials',
                'booth_space': 'Premium 20x20 booth in prime location',
                'speaking_opportunities': True,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 10,
                'email_mentions': 5,
                'additional_benefits': [
                    'Keynote speaking slot',
                    'VIP networking dinner',
                    'Dedicated social media campaign',
                    'Press release inclusion'
                ]
            },
            {
                'name': 'Gold',
                'display_order': 2,
                'color_code': '#FFD700',
                'base_price': 7500.00,
                'logo_placement': 'Stage backdrop, Website, Event programs',
                'booth_space': 'Standard 15x15 booth in high-traffic area',
                'speaking_opportunities': True,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 7,
                'email_mentions': 3,
                'additional_benefits': [
                    'Panel discussion opportunity',
                    'Networking reception access',
                    'Logo on event signage'
                ]
            },
            {
                'name': 'Silver',
                'display_order': 3,
                'color_code': '#C0C0C0',
                'base_price': 5000.00,
                'logo_placement': 'Website, Event programs, Registration area',
                'booth_space': 'Standard 10x10 booth',
                'speaking_opportunities': False,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 5,
                'email_mentions': 2,
                'additional_benefits': [
                    'Networking access',
                    'Logo in event materials',
                    'Attendee list access'
                ]
            },
            {
                'name': 'Bronze',
                'display_order': 4,
                'color_code': '#CD7F32',
                'base_price': 2500.00,
                'logo_placement': 'Website, Event programs',
                'booth_space': 'Standard 8x8 booth',
                'speaking_opportunities': False,
                'networking_access': False,
                'marketing_materials': False,
                'social_media_mentions': 2,
                'email_mentions': 1,
                'additional_benefits': [
                    'Logo recognition',
                    'Basic booth space',
                    'Event attendance'
                ]
            },
            {
                'name': 'Community',
                'display_order': 5,
                'color_code': '#4CAF50',
                'base_price': 1000.00,
                'logo_placement': 'Website sponsor section',
                'booth_space': 'Shared community area',
                'speaking_opportunities': False,
                'networking_access': False,
                'marketing_materials': False,
                'social_media_mentions': 1,
                'email_mentions': 0,
                'additional_benefits': [
                    'Logo on website',
                    'Community recognition',
                    'Event attendance'
                ]
            }
        ]

        created_count = 0
        for tier_data in default_tiers:
            tier, created = SponsorTier.objects.get_or_create(
                name=tier_data['name'],
                defaults=tier_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created sponsor tier: {tier.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Sponsor tier already exists: {tier.name}')
                )

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} sponsor tiers')
            )
        else:
            self.stdout.write(
                self.style.WARNING('No new sponsor tiers were created')
            )

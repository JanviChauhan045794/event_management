#!/usr/bin/env python
"""
Quick fix script for sponsor migration issues
Run this if you're having trouble with the migrations
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'event_manager.settings')
django.setup()

from django.db import connection
from events.models import SponsorTier

def fix_sponsor_database():
    """Fix sponsor database structure"""
    with connection.cursor() as cursor:
        try:
            # Check if SponsorTier table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_sponsortier'")
            if not cursor.fetchone():
                print("Creating SponsorTier table...")
                cursor.execute("""
                    CREATE TABLE events_sponsortier (
                        tier_id TEXT PRIMARY KEY,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        display_order INTEGER NOT NULL DEFAULT 0,
                        color_code VARCHAR(7) NOT NULL DEFAULT '#000000',
                        base_price DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                        logo_placement VARCHAR(100),
                        booth_space VARCHAR(100),
                        speaking_opportunities BOOLEAN NOT NULL DEFAULT 0,
                        networking_access BOOLEAN NOT NULL DEFAULT 0,
                        marketing_materials BOOLEAN NOT NULL DEFAULT 0,
                        social_media_mentions INTEGER NOT NULL DEFAULT 0,
                        email_mentions INTEGER NOT NULL DEFAULT 0,
                        additional_benefits TEXT,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """)
                print("SponsorTier table created successfully!")
            
            # Check if SponsorProfile table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_sponsorprofile'")
            if not cursor.fetchone():
                print("Creating SponsorProfile table...")
                cursor.execute("""
                    CREATE TABLE events_sponsorprofile (
                        profile_id TEXT PRIMARY KEY,
                        company_name VARCHAR(200) NOT NULL,
                        company_description TEXT,
                        website VARCHAR(200),
                        industry VARCHAR(100),
                        company_size VARCHAR(50),
                        primary_contact_name VARCHAR(100) NOT NULL,
                        primary_contact_email VARCHAR(254) NOT NULL,
                        primary_contact_phone VARCHAR(20),
                        primary_contact_title VARCHAR(100),
                        secondary_contact_name VARCHAR(100),
                        secondary_contact_email VARCHAR(254),
                        secondary_contact_phone VARCHAR(20),
                        secondary_contact_title VARCHAR(100),
                        address_line1 VARCHAR(255),
                        address_line2 VARCHAR(255),
                        city VARCHAR(100),
                        state_province VARCHAR(100),
                        postal_code VARCHAR(20),
                        country VARCHAR(100),
                        logo VARCHAR(100),
                        banner_image VARCHAR(100),
                        social_media_links TEXT,
                        marketing_materials VARCHAR(100),
                        notes TEXT,
                        special_requirements TEXT,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """)
                print("SponsorProfile table created successfully!")
            
            # Check current sponsor table structure
            cursor.execute("PRAGMA table_info(events_sponsor)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add missing columns to sponsor table
            if 'sponsor_profile_id' not in columns:
                print("Adding sponsor_profile_id column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN sponsor_profile_id TEXT")
            
            if 'tier_id' not in columns:
                print("Adding tier_id column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN tier_id TEXT")
            
            if 'sponsorship_amount' not in columns:
                print("Adding sponsorship_amount column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN sponsorship_amount DECIMAL(10, 2) DEFAULT 0.00")
            
            if 'contract_signed' not in columns:
                print("Adding contract_signed column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN contract_signed BOOLEAN DEFAULT 0")
            
            if 'contract_date' not in columns:
                print("Adding contract_date column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN contract_date DATE")
            
            if 'payment_received' not in columns:
                print("Adding payment_received column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN payment_received BOOLEAN DEFAULT 0")
            
            if 'payment_date' not in columns:
                print("Adding payment_date column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN payment_date DATE")
            
            if 'custom_benefits' not in columns:
                print("Adding custom_benefits column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN custom_benefits TEXT")
            
            if 'status' not in columns:
                print("Adding status column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
            
            if 'created_at' not in columns:
                print("Adding created_at column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            
            if 'updated_at' not in columns:
                print("Adding updated_at column...")
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            
            print("Database structure updated successfully!")
            
        except Exception as e:
            print(f"Error updating database: {e}")

def create_default_tiers():
    """Create default sponsor tiers"""
    try:
        from events.models import SponsorTier
        
        default_tiers = [
            {
                'name': 'Platinum',
                'display_order': 1,
                'color_code': '#E5E4E2',
                'base_price': 10000.00,
                'logo_placement': 'Main stage backdrop, Website header',
                'booth_space': 'Premium 20x20 booth',
                'speaking_opportunities': True,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 10,
                'email_mentions': 5,
            },
            {
                'name': 'Gold',
                'display_order': 2,
                'color_code': '#FFD700',
                'base_price': 7500.00,
                'logo_placement': 'Stage backdrop, Website',
                'booth_space': 'Standard 15x15 booth',
                'speaking_opportunities': True,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 7,
                'email_mentions': 3,
            },
            {
                'name': 'Silver',
                'display_order': 3,
                'color_code': '#C0C0C0',
                'base_price': 5000.00,
                'logo_placement': 'Website, Event programs',
                'booth_space': 'Standard 10x10 booth',
                'speaking_opportunities': False,
                'networking_access': True,
                'marketing_materials': True,
                'social_media_mentions': 5,
                'email_mentions': 2,
            },
            {
                'name': 'Bronze',
                'display_order': 4,
                'color_code': '#CD7F32',
                'base_price': 2500.00,
                'logo_placement': 'Website',
                'booth_space': 'Standard 8x8 booth',
                'speaking_opportunities': False,
                'networking_access': False,
                'marketing_materials': False,
                'social_media_mentions': 2,
                'email_mentions': 1,
            },
        ]
        
        created_count = 0
        for tier_data in default_tiers:
            tier, created = SponsorTier.objects.get_or_create(
                name=tier_data['name'],
                defaults=tier_data
            )
            if created:
                created_count += 1
                print(f"Created tier: {tier.name}")
        
        if created_count > 0:
            print(f"Successfully created {created_count} sponsor tiers!")
        else:
            print("All sponsor tiers already exist.")
            
    except Exception as e:
        print(f"Error creating tiers: {e}")

if __name__ == "__main__":
    print("Fixing sponsor database structure...")
    fix_sponsor_database()
    print("\nCreating default sponsor tiers...")
    create_default_tiers()
    print("\nDone! You can now visit the sponsor management page.")

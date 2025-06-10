from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import uuid
from django.utils.text import slugify

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

# --- 1. Core Tables ---
class User(AbstractUser):
    USER_TYPES = (
        ('employee', 'Employee'),
        ('student', 'Student'),
        ('industry', 'Industry Professional'),
        ('academia', 'Academic'),
        ('admin', 'Admin'),
    )
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)  # Enforced uniqueness
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=100, blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='employee')

    # Remove username (use email instead)
    username = None
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

class AttendeeType(models.Model):
    type_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)  # employee, student, etc.

    def __str__(self):
        return self.name

class ParticipantRole(models.Model):
    role_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)  # speaker, senior_chair, etc.

    def __str__(self):
        return self.name

class EventCategory(models.Model):
    category_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Event Category"
        verbose_name_plural = "Event Categories"

class EventTag(models.Model):
    tag_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_tech = models.BooleanField(default=True, help_text="Whether this is a technology-related tag")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Event Tag"
        verbose_name_plural = "Event Tags"
        ordering = ['name']

class Event(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=255)
    category = models.ForeignKey(EventCategory, on_delete=models.CASCADE)
    tags = models.ManyToManyField(EventTag, blank=True, related_name='events')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    banner = models.ImageField(upload_to='event_banners/', blank=True, null=True)
    rulebook = models.FileField(upload_to='event_rulebooks/', blank=True, null=True)
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    registration_link = models.URLField(blank=True)
    capacity = models.PositiveIntegerField(default=100, help_text="Maximum number of attendees allowed")
    enable_registration = models.BooleanField(default=True, help_text="Allow users to register for this event")

    def __str__(self):
        return self.title

    def get_category_name(self):
        return self.category.name if self.category else 'Uncategorized'

    def get_duration_in_hours(self):
        if self.start_date and self.end_date:
            duration = self.end_date - self.start_date
            return round(duration.total_seconds() / 3600, 1)
        return 0

    def is_upcoming(self):
        from django.utils import timezone
        return self.start_date > timezone.now()

    def is_ongoing(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_date <= now and self.end_date >= now

    def is_past(self):
        from django.utils import timezone
        return self.end_date < timezone.now()

    def get_status(self):
        if self.is_upcoming():
            return 'Upcoming'
        elif self.is_ongoing():
            return 'Ongoing'
        else:
            return 'Past'

    def save(self, *args, **kwargs):
        if not self.registration_link:
            from django.utils.text import slugify
            from django.urls import reverse
            slug = slugify(self.title)
            uid = uuid.uuid4().hex[:6]
            self.registration_link = f"/events/register/{slug}-{uid}"
        super().save(*args, **kwargs)

    def get_registration_url(self):
        """Get the full registration URL for the event"""
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        return f"https://{current_site.domain}{self.registration_link}"

    def get_available_seats(self):
        """Calculate the number of available seats for the event"""
        from django.db.models import Count
        attendee_count = self.registration_set.filter(role__name='attendee').count()
        return max(0, self.capacity - attendee_count)

    def is_full(self):
        """Check if the event is at full capacity"""
        return self.get_available_seats() <= 0

    def get_sponsor_leads(self, user):
        """Get the number of leads generated for a sponsor."""
        sponsor = self.sponsors.get(user=user)
        return Registration.objects.filter(
            event=self,
            sponsor_interactions__sponsor=sponsor,
            sponsor_interactions__is_lead=True
        ).count()

    def get_sponsor_engagement(self, user):
        """Get the engagement score for a sponsor."""
        sponsor = self.sponsors.get(user=user)
        interactions = sponsor.interactions.filter(event=self)
        if not interactions.exists():
            return 0
        
        total_score = sum(interaction.engagement_score for interaction in interactions)
        return total_score / interactions.count()

    def get_sponsor_booth_visits(self, user):
        """Get the number of booth visits for a sponsor."""
        sponsor = self.sponsors.get(user=user)
        return sponsor.interactions.filter(
            event=self,
            interaction_type='booth_visit'
        ).count()

    def get_sponsor_material_downloads(self, user):
        """Get the total number of material downloads for a sponsor."""
        sponsor = self.sponsors.get(user=user)
        return sum(
            material.download_count 
            for material in sponsor.materials.filter(event=self)
        )

    def get_sponsor_contact_requests(self, user):
        """Get the number of contact requests for a sponsor."""
        sponsor = self.sponsors.get(user=user)
        return sponsor.interactions.filter(
            event=self,
            interaction_type='contact_request'
        ).count()

# --- 2. Hackathon-Specific Tables ---
class HackathonTeam(models.Model):
    team_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.event.title}"

class TeamMember(models.Model):
    member_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    attendee_type = models.ForeignKey(AttendeeType, on_delete=models.SET_NULL, null=True)  # Added

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.team.name}"

# --- 3. Conference/Seminar Tables ---
class PaperSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )
    paper_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

class Track(models.Model):
    track_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # AI, DevOps, etc.

    def __str__(self):
        return f"{self.name} - {self.event.title}"

# --- 4. Speaker & Sponsor Tables ---
class Speaker(models.Model):
    speaker_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bio = models.TextField()
    social_links = models.JSONField(default=dict)  # Requires PostgreSQL
    materials = models.FileField(upload_to='speaker_materials/', blank=True, null=True,
                               help_text="Upload presentation materials (limit: 50MB)")

    def __str__(self):
        return self.user.get_full_name() or self.user.email

class EventSpeaker(models.Model):
    """Model to link speakers to events with additional information"""
    event_speaker_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='event_speakers')
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE, related_name='speaking_events')
    topic = models.CharField(max_length=255, blank=True, help_text="Topic or title of the speaker's presentation")
    presentation_time = models.DateTimeField(null=True, blank=True, help_text="Scheduled time for the presentation")
    duration_minutes = models.PositiveIntegerField(default=30, help_text="Duration of the presentation in minutes")
    is_keynote = models.BooleanField(default=False, help_text="Whether this is a keynote presentation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'speaker')
        ordering = ['presentation_time', 'created_at']

    def __str__(self):
        return f"{self.speaker} at {self.event.title}"

# --- Sponsor Tier Model ---
class SponsorTier(models.Model):
    """Model to define different sponsorship tiers with their benefits"""
    tier_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)  # e.g., "Platinum", "Gold", "Silver", "Bronze"
    display_order = models.PositiveIntegerField(default=0, help_text="Order for displaying tiers (lower numbers first)")
    color_code = models.CharField(max_length=7, default="#000000", help_text="Hex color code for the tier")

    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Benefits
    logo_placement = models.CharField(max_length=100, blank=True, help_text="Where the sponsor logo will be placed")
    booth_space = models.CharField(max_length=100, blank=True, help_text="Booth space allocation")
    speaking_opportunities = models.BooleanField(default=False)
    networking_access = models.BooleanField(default=False)
    marketing_materials = models.BooleanField(default=False)
    social_media_mentions = models.PositiveIntegerField(default=0, help_text="Number of social media mentions")
    email_mentions = models.PositiveIntegerField(default=0, help_text="Number of email newsletter mentions")

    # Additional benefits (JSON field for flexibility)
    additional_benefits = models.JSONField(default=list, blank=True, help_text="List of additional benefits")

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Sponsor Tier"
        verbose_name_plural = "Sponsor Tiers"

    def __str__(self):
        return self.name


# --- Sponsor Profile Model ---
class SponsorProfile(models.Model):
    """Model to store detailed sponsor company information"""
    profile_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Company Information
    company_name = models.CharField(max_length=200)
    company_description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True, help_text="e.g., '1-50 employees', '500+ employees'")

    # Contact Information
    primary_contact_name = models.CharField(max_length=100)
    primary_contact_email = models.EmailField()
    primary_contact_phone = models.CharField(max_length=20, blank=True)
    primary_contact_title = models.CharField(max_length=100, blank=True)

    # Secondary contact (optional)
    secondary_contact_name = models.CharField(max_length=100, blank=True)
    secondary_contact_email = models.EmailField(blank=True)
    secondary_contact_phone = models.CharField(max_length=20, blank=True)
    secondary_contact_title = models.CharField(max_length=100, blank=True)

    # Address Information
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Media Assets
    logo = models.ImageField(upload_to='sponsor_logos/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='sponsor_banners/', blank=True, null=True)

    # Social Media
    social_media_links = models.JSONField(default=dict, blank=True, help_text="Social media links")

    # Marketing Materials
    marketing_materials = models.FileField(upload_to='sponsor_materials/', blank=True, null=True,
                                         help_text="Marketing materials, brochures, etc.")

    # Notes and Special Requirements
    notes = models.TextField(blank=True, help_text="Internal notes about the sponsor")
    special_requirements = models.TextField(blank=True, help_text="Special requirements or requests")

    # Preferences
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notification preferences for different types of updates"
    )
    display_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Display preferences for public profile"
    )

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['company_name']
        verbose_name = "Sponsor Profile"
        verbose_name_plural = "Sponsor Profiles"

    def __str__(self):
        return self.company_name

    def get_default_notification_preferences(self):
        """Get default notification preferences."""
        return {
            'event_updates': True,
            'attendee_interactions': True,
            'analytics_reports': True,
            'material_downloads': True
        }

    def get_default_display_preferences(self):
        """Get default display preferences."""
        return {
            'show_logo': True,
            'show_description': True,
            'show_contact': True,
            'show_website': True
        }

    def save(self, *args, **kwargs):
        # Set default preferences if not set
        if not self.notification_preferences:
            self.notification_preferences = self.get_default_notification_preferences()
        if not self.display_preferences:
            self.display_preferences = self.get_default_display_preferences()
        super().save(*args, **kwargs)

# --- Enhanced Sponsor Model ---
class Sponsor(models.Model):
    """Model linking sponsor profiles to specific events with tier information"""
    sponsor_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sponsors')

    # Legacy fields for backward compatibility
    name = models.CharField(max_length=100, blank=True, null=True)
    tier_legacy = models.CharField(max_length=20, choices=[('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')], blank=True, null=True)

    # Enhanced fields (nullable for migration compatibility)
    sponsor_profile = models.ForeignKey(SponsorProfile, on_delete=models.CASCADE, related_name='sponsorships', null=True, blank=True)
    tier = models.ForeignKey(SponsorTier, on_delete=models.CASCADE, related_name='sponsors', null=True, blank=True)

    # Sponsorship Details
    sponsorship_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    contract_signed = models.BooleanField(default=False)
    contract_date = models.DateField(null=True, blank=True)
    payment_received = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)

    # Custom benefits for this specific sponsorship
    custom_benefits = models.JSONField(default=list, blank=True, help_text="Custom benefits for this sponsorship")

    # Status
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        unique_together = ('event', 'sponsor_profile')
        ordering = ['tier__display_order', 'sponsor_profile__company_name']
        verbose_name = "Event Sponsor"
        verbose_name_plural = "Event Sponsors"

    def __str__(self):
        if self.sponsor_profile and self.tier:
            return f"{self.sponsor_profile.company_name} - {self.tier.name} Sponsor for {self.event.title}"
        elif self.name:
            return f"{self.name} - Sponsor for {self.event.title}"
        else:
            return f"Sponsor for {self.event.title}"

    def save(self, *args, **kwargs):
        # Auto-populate name field if not provided
        if not self.name and self.sponsor_profile:
            self.name = self.sponsor_profile.company_name
        elif not self.name:
            self.name = f"Sponsor for {self.event.title}"
        super().save(*args, **kwargs)

    def get_company_name(self):
        """Get the company name from profile or name field"""
        if self.sponsor_profile:
            return self.sponsor_profile.company_name
        return self.name or "Unknown Sponsor"

# --- 5. Logistics & Feedback ---
class Venue(models.Model):
    venue_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    capacity = models.IntegerField()

    def __str__(self):
        return f"{self.name} (Capacity: {self.capacity})"

class Feedback(models.Model):
    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comments = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Feedback for {self.event.title} by {self.user.get_full_name() or self.user.email}"

    class Meta:
        ordering = ['-created_at']

# --- 6. Access Control ---
class Permission(models.Model):
    permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(ParticipantRole, on_delete=models.CASCADE)
    can_edit = models.BooleanField(default=False)
    can_invite = models.BooleanField(default=False)

    def __str__(self):
        permissions = []
        if self.can_edit:
            permissions.append('Edit')
        if self.can_invite:
            permissions.append('Invite')
        permission_str = ', '.join(permissions) if permissions else 'No permissions'
        return f"{self.role.name}: {permission_str}"

# --- 7. Notifications ---
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('event_reminder', 'Event Reminder'),
        ('registration', 'Registration Update'),
        ('event_update', 'Event Update'),
        ('feedback', 'Feedback Request'),
        ('system', 'System Notification'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

# --- Registration (Connects Users to Events) ---
class Registration(models.Model):
    registration_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(ParticipantRole, on_delete=models.CASCADE)
    attendee_type = models.ForeignKey(AttendeeType, on_delete=models.SET_NULL, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    # Notification preferences
    reminders_enabled = models.BooleanField(default=True)
    updates_enabled = models.BooleanField(default=True)

    # Additional attendee information
    dietary_requirements = models.CharField(max_length=255, blank=True, null=True)
    special_assistance = models.CharField(max_length=255, blank=True, null=True)

    # Registration status
    STATUS_CHOICES = (
        ('registered', 'Registered'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('waitlisted', 'Waitlisted'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')

    # Payment status (if applicable)
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)

    # Check-in status
    checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    # Terms agreement
    agreed_to_terms = models.BooleanField(default=False)

    def __str__(self):
        attendee_type_str = f" ({self.attendee_type})" if self.attendee_type else ""
        return f"{self.user.get_full_name() or self.user.email} - {self.event.title} - {self.role}{attendee_type_str}"

    class Meta:
        verbose_name = "Registration"
        verbose_name_plural = "Registrations"
        unique_together = ('event', 'user')

# --- 8. Admin Dashboard Models ---
class SiteSettings(models.Model):
    settings_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_name = models.CharField(max_length=100, default="CorpEventX")
    site_logo = models.ImageField(upload_to='site_assets/', blank=True, null=True)
    favicon = models.ImageField(upload_to='site_assets/', blank=True, null=True)
    primary_color = models.CharField(max_length=20, default="#3498db")
    secondary_color = models.CharField(max_length=20, default="#2c3e50")
    footer_text = models.TextField(default="© 2025 CorpEventX. All rights reserved.")
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Site Settings - {self.site_name}"

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

class BlogCategory(models.Model):
    category_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"

class BlogPost(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )

    post_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    featured_image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    allow_comments = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

class BlogComment(models.Model):
    comment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Comment by {self.author.get_full_name() or self.author.email} on {self.post.title}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Blog Comment"
        verbose_name_plural = "Blog Comments"

class ContactInformation(models.Model):
    contact_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    google_maps_embed = models.TextField(blank=True, help_text="Paste the Google Maps embed code here")
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    contact_form_recipients = models.TextField(blank=True, help_text="Comma-separated list of email addresses")

    def __str__(self):
        return f"Contact Information"

    class Meta:
        verbose_name = "Contact Information"
        verbose_name_plural = "Contact Information"

class ContactMessage(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('spam', 'Spam'),
    )

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Admin notes about this message")

    def __str__(self):
        return f"{self.subject} from {self.name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

class CheckIn(models.Model):
    checkin_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='checkins')
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='performed_checkins')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Check-in: {self.registration.user.get_full_name() or self.registration.user.email} for {self.registration.event.title}"

    class Meta:
        verbose_name = "Check-In"
        verbose_name_plural = "Check-Ins"
        ordering = ['-checked_in_at']

class Revenue(models.Model):
    revenue_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='revenues')
    total_tickets_sold = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Revenue for {self.event.title}"

    def calculate_net_profit(self):
        self.net_profit = self.total_revenue - self.expenses
        self.save()

    class Meta:
        verbose_name = "Revenue"
        verbose_name_plural = "Revenues"

class AdminDashboardSettings(models.Model):
    settings_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_settings')
    dashboard_theme = models.CharField(max_length=20, default='light')
    items_per_page = models.IntegerField(default=10)
    show_revenue_stats = models.BooleanField(default=True)
    show_user_stats = models.BooleanField(default=True)
    show_event_stats = models.BooleanField(default=True)

    def __str__(self):
        return f"Admin Settings for {self.user.get_full_name() or self.user.email}"

    class Meta:
        verbose_name = "Admin Dashboard Settings"
        verbose_name_plural = "Admin Dashboard Settings"

class SponsorMaterial(models.Model):
    """Model for storing event-specific sponsor marketing materials."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name='materials')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sponsor_materials')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='sponsor_materials/%Y/%m/')
    description = models.TextField(blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    download_count = models.IntegerField(default=0)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ['-upload_date']
        verbose_name = "Sponsor Material"
        verbose_name_plural = "Sponsor Materials"

    def __str__(self):
        return f"{self.name} - {self.sponsor.get_company_name()} ({self.event.title})"

    def increment_downloads(self):
        """Increment the download counter."""
        self.download_count += 1
        self.save()

class SponsorInteraction(models.Model):
    """Model for tracking attendee interactions with sponsors."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name='interactions')
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    attendee = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='sponsor_interactions')
    
    INTERACTION_TYPES = [
        ('booth_visit', 'Booth Visit'),
        ('material_download', 'Material Download'),
        ('contact_request', 'Contact Request'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        ('demo_attended', 'Demo Attended'),
        ('survey_completed', 'Survey Completed'),
        ('other', 'Other')
    ]
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    is_lead = models.BooleanField(default=False)
    engagement_score = models.IntegerField(default=1)
    follow_up_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('contacted', 'Contacted'),
            ('responded', 'Responded'),
            ('converted', 'Converted'),
            ('closed', 'Closed')
        ],
        default='pending'
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Sponsor Interaction"
        verbose_name_plural = "Sponsor Interactions"

    def __str__(self):
        return f"{self.get_interaction_type_display()} - {self.sponsor.get_company_name()} - {self.attendee.user.get_full_name()}"

    def save(self, *args, **kwargs):
        # Set engagement score based on interaction type
        engagement_scores = {
            'booth_visit': 1,
            'material_download': 2,
            'contact_request': 3,
            'meeting_scheduled': 4,
            'demo_attended': 5,
            'survey_completed': 3,
            'other': 1
        }
        self.engagement_score = engagement_scores.get(self.interaction_type, 1)
        super().save(*args, **kwargs)
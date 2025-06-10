from django.contrib import admin
from django.db.models import Q, Count, Sum
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _

# Register your models here.
from .models import *

# Customize admin site
class CorpEventXAdminSite(AdminSite):
    site_title = _('CorpEventX Admin')
    site_header = _('CorpEventX Administration')
    index_title = _('CorpEventX Management')

# Create custom admin site instance
admin_site = CorpEventXAdminSite(name='corpeventx_admin')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'get_role', 'get_attendee_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'user_type', 'company')
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    ordering = ('-date_joined',)
    fieldsets = (
        ('Personal Information', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'company', 'user_type')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    filter_horizontal = ('groups', 'user_permissions',)
    actions = ['approve_speakers', 'make_staff', 'make_regular_user']

    def get_role(self, obj):
        # Get the most recent registration for this user
        registration = Registration.objects.filter(user=obj).order_by('-registered_at').first()
        if registration:
            role_name = registration.role.name

            # Check if this is a speaker that needs approval
            if role_name == 'speaker':
                # Check if they have a Speaker object (approved) or are staff
                is_approved = obj.is_staff or Speaker.objects.filter(user=obj).exists()
                if not is_approved:
                    return format_html('<span style="color:orange;">{} (Pending Approval)</span>', role_name)
                return format_html('<span style="color:green;">{} (Approved)</span>', role_name)

            return role_name
        return '-'
    get_role.short_description = 'Role'

    def get_attendee_type(self, obj):
        # Get the most recent registration for this user
        registration = Registration.objects.filter(user=obj).order_by('-registered_at').first()
        if registration and registration.attendee_type:
            return registration.attendee_type.name
        return '-'
    get_attendee_type.short_description = 'Attendee Type'

    def approve_speakers(self, request, queryset):
        # Find users with speaker role and approve them
        for user in queryset:
            registration = Registration.objects.filter(user=user, role__name='speaker').first()
            if registration:
                user.is_staff = True
                user.save()
        self.message_user(request, f"{queryset.count()} speakers have been approved.")
    approve_speakers.short_description = "Approve selected speakers"

    def make_staff(self, request, queryset):
        queryset.update(is_staff=True)
        self.message_user(request, f"{queryset.count()} users have been granted staff status.")
    make_staff.short_description = "Grant staff status to selected users"

    def make_regular_user(self, request, queryset):
        queryset.update(is_staff=False, is_superuser=False)
        self.message_user(request, f"{queryset.count()} users have been set as regular users.")
    make_regular_user.short_description = "Remove staff status from selected users"

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'category', 'organizer', 'get_status', 'get_registrations_count', 'get_revenue')
    list_filter = ('category', 'start_date', 'organizer')
    search_fields = ('title', 'description', 'location', 'organizer__email')
    date_hierarchy = 'start_date'
    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'category', 'organizer', 'banner', 'rulebook')
        }),
        ('Date and Location', {
            'fields': ('start_date', 'end_date', 'location')
        }),
        ('Pricing', {
            'fields': ('ticket_price',)
        }),
        ('Registration', {
            'fields': ('registration_link',)
        }),
    )

    def get_status(self, obj):
        status = obj.get_status()
        if status == 'Upcoming':
            return format_html('<span style="color:blue;">{}</span>', status)
        elif status == 'Ongoing':
            return format_html('<span style="color:green;">{}</span>', status)
        else:
            return format_html('<span style="color:gray;">{}</span>', status)
    get_status.short_description = 'Status'

    def get_registrations_count(self, obj):
        count = Registration.objects.filter(event=obj).count()
        return count
    get_registrations_count.short_description = 'Registrations'

    def get_revenue(self, obj):
        revenue = Revenue.objects.filter(event=obj).first()
        if revenue:
            return f"${revenue.total_revenue}"
        return "$0.00"
    get_revenue.short_description = 'Revenue'

@admin.register(HackathonTeam)
class HackathonTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'score')

@admin.register(PaperSubmission)
class PaperSubmissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'status')

# Enhanced admin classes for existing models
@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'role', 'attendee_type', 'registered_at', 'get_check_in_status')
    list_filter = ('role', 'attendee_type', 'registered_at', 'event')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'event__title')
    date_hierarchy = 'registered_at'

    def get_check_in_status(self, obj):
        checkin = CheckIn.objects.filter(registration=obj).first()
        if checkin:
            return format_html('<span style="color:green;">✓ Checked in at {}</span>', checkin.checked_in_at.strftime('%Y-%m-%d %H:%M'))
        return format_html('<span style="color:red;">✗ Not checked in</span>')
    get_check_in_status.short_description = 'Check-in Status'

@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_full_name', 'get_email', 'get_events_count')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'bio')

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def get_events_count(self, obj):
        count = Registration.objects.filter(user=obj.user, role__name='speaker').count()
        return count
    get_events_count.short_description = 'Events'

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'rating', 'get_comments_preview', 'created_at')
    list_filter = ('rating', 'event', 'created_at')
    search_fields = ('event__title', 'user__email', 'comments')

    def get_comments_preview(self, obj):
        if len(obj.comments) > 50:
            return obj.comments[:50] + '...'
        return obj.comments
    get_comments_preview.short_description = 'Comments'

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_events_count')
    search_fields = ('name',)

    def get_events_count(self, obj):
        return Event.objects.filter(category=obj).count()
    get_events_count.short_description = 'Events'

@admin.register(ParticipantRole)
class ParticipantRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_users_count')
    search_fields = ('name',)

    def get_users_count(self, obj):
        return Registration.objects.filter(role=obj).count()
    get_users_count.short_description = 'Users'

@admin.register(AttendeeType)
class AttendeeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_users_count')
    search_fields = ('name',)

    def get_users_count(self, obj):
        return Registration.objects.filter(attendee_type=obj).count()
    get_users_count.short_description = 'Users'

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity')
    search_fields = ('name',)

@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ('get_sponsor_name', 'event', 'get_tier_name', 'get_sponsorship_amount', 'get_status')
    list_filter = ('event', 'status')
    search_fields = ('event__title', 'sponsor_profile__company_name', 'name')
    fieldsets = (
        ('Basic Information', {
            'fields': ('event', 'name')
        }),
        ('Enhanced Information', {
            'fields': ('sponsor_profile', 'tier', 'sponsorship_amount'),
            'description': 'Use these fields for enhanced sponsor management'
        }),
        ('Legacy Information', {
            'fields': ('tier_legacy',),
            'classes': ('collapse',),
            'description': 'Legacy tier field for backward compatibility'
        }),
        ('Contract & Payment', {
            'fields': ('contract_signed', 'contract_date', 'payment_received', 'payment_date', 'status'),
        }),
        ('Additional Information', {
            'fields': ('custom_benefits',),
            'classes': ('collapse',),
        }),
    )

    def get_sponsor_name(self, obj):
        if hasattr(obj, 'sponsor_profile') and obj.sponsor_profile:
            return obj.sponsor_profile.company_name
        elif hasattr(obj, 'name') and obj.name:
            return obj.name
        else:
            return f"Sponsor {str(obj.sponsor_id)[:8]}"
    get_sponsor_name.short_description = 'Company Name'

    def get_tier_name(self, obj):
        if hasattr(obj, 'tier') and obj.tier:
            return obj.tier.name
        elif hasattr(obj, 'tier_legacy') and obj.tier_legacy:
            return obj.tier_legacy.title()
        else:
            return '-'
    get_tier_name.short_description = 'Tier'

    def get_sponsorship_amount(self, obj):
        if hasattr(obj, 'sponsorship_amount'):
            return f"₹{obj.sponsorship_amount:,.2f}"
        return '-'
    get_sponsorship_amount.short_description = 'Amount'

    def get_status(self, obj):
        if hasattr(obj, 'status'):
            status_colors = {
                'pending': 'orange',
                'confirmed': 'blue',
                'active': 'green',
                'completed': 'gray',
                'cancelled': 'red'
            }
            color = status_colors.get(obj.status, 'black')
            return format_html('<span style="color:{};">{}</span>', color, obj.status.title())
        return '-'
    get_status.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        # Auto-populate name field if not provided
        if not obj.name and obj.sponsor_profile:
            obj.name = obj.sponsor_profile.company_name
        elif not obj.name:
            obj.name = f"Sponsor for {obj.event.title}"

        super().save_model(request, obj, form, change)

# Enhanced Sponsor Management Admin
@admin.register(SponsorTier)
class SponsorTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_base_price', 'display_order', 'get_color_preview', 'get_sponsors_count')
    list_editable = ('display_order',)
    search_fields = ('name',)
    ordering = ('display_order', 'name')

    def get_base_price(self, obj):
        return f"₹{obj.base_price:,.2f}"
    get_base_price.short_description = 'Base Price'

    def get_color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div>',
            obj.color_code
        )
    get_color_preview.short_description = 'Color'

    def get_sponsors_count(self, obj):
        return Sponsor.objects.filter(tier=obj).count()
    get_sponsors_count.short_description = 'Active Sponsors'

@admin.register(SponsorProfile)
class SponsorProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'industry', 'primary_contact_name', 'primary_contact_email', 'is_active', 'get_sponsorships_count')
    list_filter = ('industry', 'is_active', 'created_at')
    search_fields = ('company_name', 'primary_contact_name', 'primary_contact_email', 'industry')
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'company_description', 'website', 'industry', 'company_size', 'logo', 'banner_image')
        }),
        ('Primary Contact', {
            'fields': ('primary_contact_name', 'primary_contact_email', 'primary_contact_phone', 'primary_contact_title')
        }),
        ('Secondary Contact', {
            'fields': ('secondary_contact_name', 'secondary_contact_email', 'secondary_contact_phone', 'secondary_contact_title')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state_province', 'postal_code', 'country')
        }),
        ('Additional Information', {
            'fields': ('social_media_links', 'marketing_materials', 'notes', 'special_requirements', 'is_active')
        }),
    )

    def get_sponsorships_count(self, obj):
        return Sponsor.objects.filter(sponsor_profile=obj).count()
    get_sponsorships_count.short_description = 'Sponsorships'

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'team', 'attendee_type')
    list_filter = ('attendee_type', 'team__event')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'team__name')

# Register new admin dashboard models
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'last_updated', 'maintenance_mode')
    fieldsets = (
        ('Basic Information', {
            'fields': ('site_name', 'site_logo', 'favicon', 'footer_text')
        }),
        ('Colors', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords', 'google_analytics_id')
        }),
        ('Maintenance', {
            'fields': ('maintenance_mode', 'maintenance_message')
        }),
    )

    def has_add_permission(self, request):
        # Check if there's already a site settings object
        return SiteSettings.objects.count() == 0

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'get_posts_count')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

    def get_posts_count(self, obj):
        return BlogPost.objects.filter(category=obj).count()
    get_posts_count.short_description = 'Posts'

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'status', 'published_at', 'get_comments_count')
    list_filter = ('status', 'category', 'published_at')
    search_fields = ('title', 'content', 'author__email')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    fieldsets = (
        ('Post Information', {
            'fields': ('title', 'slug', 'content', 'excerpt', 'featured_image', 'category', 'author', 'status')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords')
        }),
        ('Options', {
            'fields': ('allow_comments',)
        }),
    )

    def get_comments_count(self, obj):
        return BlogComment.objects.filter(post=obj).count()
    get_comments_count.short_description = 'Comments'

@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'author', 'created_at', 'is_approved', 'get_content_preview')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('content', 'author__email', 'post__title')
    actions = ['approve_comments', 'unapprove_comments']

    def get_content_preview(self, obj):
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    get_content_preview.short_description = 'Content'

    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Approve selected comments"

    def unapprove_comments(self, request, queryset):
        queryset.update(is_approved=False)
    unapprove_comments.short_description = "Unapprove selected comments"

@admin.register(ContactInformation)
class ContactInformationAdmin(admin.ModelAdmin):
    list_display = ('email', 'phone', 'get_address_preview')
    fieldsets = (
        ('Contact Details', {
            'fields': ('email', 'phone', 'address', 'google_maps_embed')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url')
        }),
        ('Form Settings', {
            'fields': ('contact_form_recipients',)
        }),
    )

    def get_address_preview(self, obj):
        if len(obj.address) > 50:
            return obj.address[:50] + '...'
        return obj.address
    get_address_preview.short_description = 'Address'

    def has_add_permission(self, request):
        # Check if there's already a contact information object
        return ContactInformation.objects.count() == 0

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'created_at')
    fieldsets = (
        ('Message Information', {
            'fields': ('name', 'email', 'subject', 'message', 'created_at')
        }),
        ('Admin', {
            'fields': ('status', 'notes')
        }),
    )
    actions = ['mark_as_resolved', 'mark_as_spam']

    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')
    mark_as_resolved.short_description = "Mark selected messages as resolved"

    def mark_as_spam(self, request, queryset):
        queryset.update(status='spam')
    mark_as_spam.short_description = "Mark selected messages as spam"

@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('registration', 'get_event', 'get_user', 'checked_in_at', 'checked_in_by')
    list_filter = ('checked_in_at', 'registration__event')
    search_fields = ('registration__user__email', 'registration__event__title', 'notes')
    date_hierarchy = 'checked_in_at'

    def get_event(self, obj):
        return obj.registration.event
    get_event.short_description = 'Event'

    def get_user(self, obj):
        return obj.registration.user
    get_user.short_description = 'User'

@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = ('event', 'total_tickets_sold', 'total_revenue', 'expenses', 'net_profit', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('event__title',)
    readonly_fields = ('net_profit',)

    def save_model(self, request, obj, form, change):
        obj.calculate_net_profit()
        super().save_model(request, obj, form, change)

@admin.register(AdminDashboardSettings)
class AdminDashboardSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'dashboard_theme', 'items_per_page')
    list_filter = ('dashboard_theme', 'show_revenue_stats', 'show_user_stats', 'show_event_stats')
    search_fields = ('user__email',)
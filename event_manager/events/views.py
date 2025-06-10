from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from .forms import CustomUserCreationForm, EventForm, EventRegistrationForm, SponsorProfileForm, SponsorTierForm, SponsorForm
from .models import User, ParticipantRole, AttendeeType, Event, EventCategory, Registration, Feedback, Sponsor, Speaker, Notification, EventSpeaker, SponsorTier, SponsorProfile, SponsorMaterial, EventTag
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import json
import csv
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.paginator import Paginator
from django.template.loader import get_template
import os
from xhtml2pdf import pisa
from django.conf import settings
from django.db import models
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .utils import generate_qr_code_base64, parse_location, generate_event_ticket
from django.db.models import Q
from datetime import datetime, timedelta
from icalendar import Calendar, Event as ICalEvent
import pytz
from django.db.models import Count, Avg
from io import BytesIO
import logging
import qrcode
import base64
import hashlib
import traceback
from smtplib import SMTPException, SMTPAuthenticationError
import requests
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse

# Configure logger
logger = logging.getLogger(__name__)

# Create your views here.
def test_qr_code(request):
    """
    Test view to verify QR code generation is working
    """
    test_data = "This is a test QR code"
    qr_code_base64 = generate_qr_code_base64(test_data)

    # Get a sample event for testing
    event = Event.objects.first()

    # Create a context similar to what we'd use in the event_pdf view
    context = {
        'event': event,
        'user': request.user if request.user.is_authenticated else None,
        'registration': Registration.objects.filter(event=event, user=request.user).first() if request.user.is_authenticated else None,
        'qr_code': qr_code_base64,
        'now': timezone.now(),
    }

    # Render the simple ticket template
    template = get_template('simple_ticket.html')
    html = template.render(context)

    return HttpResponse(html)

def index(request):
    """
    View function for the landing page.
    """
    return render(request, 'index.html')

def user_type_selection(request):
    """
    View function for the user type selection page.
    """
    return render(request, 'user_type_selection.html')

def register(request):
    """
    View function for the registration form.
    """
    # Get the user type from the form submission
    user_type = request.POST.get('user_type')

    # If no user type is provided, redirect to the user type selection page
    if not user_type:
        return redirect('user_type_selection')

    # Create a form instance with the user type pre-selected
    initial_data = {'user_type': user_type}
    form = CustomUserCreationForm(initial=initial_data)

    return render(request, 'register.html', {
        'form': form,
        'user_type': user_type
    })

def register_submit(request):
    """
    View function to handle the registration form submission.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            # Save the user
            user = form.save()

            # Get the role and attendee type
            role_name = form.cleaned_data.get('role')
            attendee_type_name = form.cleaned_data.get('attendee_type')

            # Get the role and attendee type objects
            role = ParticipantRole.objects.get(name=role_name)

            # If the user is an attendee, get the attendee type
            attendee_type = None
            if role_name == 'attendee' and attendee_type_name:
                attendee_type = AttendeeType.objects.get(name=attendee_type_name)

            # Create a default event for new users if needed
            # This is a temporary solution - in a real application, you might want to
            # handle this differently, such as creating a "Welcome" event or
            # waiting until the user registers for an actual event
            default_category, _ = EventCategory.objects.get_or_create(name='Default')
            default_event, created = Event.objects.get_or_create(
                title='Welcome Event',
                defaults={
                    'description': 'Welcome to the Event Manager platform',
                    'start_date': timezone.now(),
                    'end_date': timezone.now() + timezone.timedelta(days=30),
                    'location': 'Online',
                    'organizer': user,
                    'category': default_category,
                }
            )

            # Create a registration record for the user
            Registration.objects.create(
                event=default_event,
                user=user,
                role=role,
                attendee_type=attendee_type
            )

            # Log the user in
            login(request, user)

            # Redirect to the success page
            return redirect('registration_success')
    else:
        # If the request method is not POST, redirect to the user type selection page
        return redirect('user_type_selection')

    # If the form is not valid, render the registration form with errors
    return render(request, 'register.html', {
        'form': form,
        'user_type': form.cleaned_data.get('user_type') if form.is_bound else None
    })

@login_required
def registration_success(request):
    messages.success(request, 'Registration successful! Please log in to access your dashboard.')
    return redirect('login')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            # Check if user is admin/staff first
            if user.is_staff or user.user_type == 'admin':
                return redirect('admin_dashboard')

            # Find the user's most recent registration and get their role
            try:
                latest_registration = Registration.objects.filter(
                    user=user
                ).select_related('role').latest('registered_at')

                role_name = latest_registration.role.name

                # Redirect based on role
                if role_name == 'organizer':
                    return redirect('organizer_dashboard')
                elif role_name == 'speaker':
                    return redirect('speaker_dashboard')
                elif role_name == 'attendee':
                    return redirect('attendee_dashboard')
                else:
                    # Default dashboard redirect
                    return redirect('dashboard')

            except Registration.DoesNotExist:
                # If no registration exists, use user_type as fallback
                if user.user_type == 'organizer':
                    return redirect('organizer_dashboard')
                elif user.user_type == 'speaker':
                    return redirect('speaker_dashboard')
                else:  # attendee or other
                    return redirect('attendee_dashboard')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'login.html')

@login_required
def dashboard_redirect(request):
    """
    Redirect users to their appropriate dashboard based on role.
    This is a fallback view in case the direct dashboard URLs are accessed.
    """
    # Check if user is admin/staff first
    if request.user.is_staff or request.user.user_type == 'admin':
        return redirect('admin_dashboard')

    try:
        # Find the user's most recent registration and get their role
        latest_registration = Registration.objects.filter(
            user=request.user
        ).select_related('role').latest('registered_at')

        role_name = latest_registration.role.name

        # Redirect based on role
        if role_name == 'organizer':
            return redirect('organizer_dashboard')
        elif role_name == 'speaker':
            return redirect('speaker_dashboard')
        elif role_name == 'attendee':
            return redirect('attendee_dashboard')

    except Registration.DoesNotExist:
        # If no registration exists, use user_type as fallback
        if request.user.user_type == 'organizer':
            return redirect('organizer_dashboard')
        elif request.user.user_type == 'speaker':
            return redirect('speaker_dashboard')
        else:  # attendee or other
            return redirect('attendee_dashboard')

    # Default to attendee dashboard if all else fails
    return redirect('attendee_dashboard')

@login_required
def speaker_dashboard(request):
    """
    View function for the speaker dashboard.
    """
    # Get the current user's speaker profile
    try:
        speaker = Speaker.objects.get(user=request.user)
    except Speaker.DoesNotExist:
        # Create a speaker profile if it doesn't exist
        speaker = Speaker.objects.create(
            user=request.user,
            bio=f"Bio for {request.user.get_full_name() or request.user.email}"
        )

    # Get the current user's events where they are a speaker
    speaker_events = Event.objects.filter(
        registration__user=request.user,
        registration__role__name='speaker'
    ).distinct()

    # Get upcoming events where the user is a speaker
    upcoming_events = speaker_events.filter(
        start_date__gte=timezone.now()
    ).order_by('start_date')[:5]

    # Get past events where the user is a speaker
    past_events = speaker_events.filter(
        end_date__lt=timezone.now()
    ).order_by('-end_date')[:5]

    # Get feedback for the user's speaking engagements
    feedback = Feedback.objects.filter(
        event__in=speaker_events
    ).order_by('-feedback_id')[:5]

    # Calculate total attendees
    total_attendees = 0
    for event in past_events:
        total_attendees += Registration.objects.filter(event=event).count()

    # Calculate average rating
    avg_rating = 0
    if feedback.exists():
        total_rating = sum(item.rating for item in feedback)
        avg_rating = total_rating / feedback.count()

    # Get today's date
    today = timezone.now().date()
    formatted_date = today.strftime('%B %d, %Y')  # Format example: January 01, 2023

    # Prepare chart data for attendee trends
    event_dates = []
    attendee_counts = []

    for event in past_events:
        event_dates.append(event.start_date.strftime('%b %d'))
        attendee_counts.append(Registration.objects.filter(event=event).count())

    # Prepare chart data for feedback distribution
    rating_distribution = [0, 0, 0, 0, 0]  # 5 stars, 4 stars, 3 stars, 2 stars, 1 star

    for item in Feedback.objects.filter(event__in=speaker_events):
        if 1 <= item.rating <= 5:
            rating_distribution[5 - item.rating] += 1

    # Get speaker assignment notifications
    speaker_notifications = Notification.objects.filter(
        user=request.user,
        notification_type='speaker_added'
    ).order_by('-created_at')[:5]

    # Get all events where the user is assigned as a speaker through EventSpeaker
    assigned_events = EventSpeaker.objects.filter(
        speaker=speaker
    ).select_related('event').order_by('event__start_date')

    # Filter to only show upcoming assigned events
    upcoming_assigned_events = assigned_events.filter(
        event__start_date__gte=timezone.now()
    )[:5]

    # Convert data to JSON strings to safely embed in template
    import json
    event_dates_json = json.dumps(event_dates)
    attendee_counts_json = json.dumps(attendee_counts)
    rating_distribution_json = json.dumps(rating_distribution)

    context = {
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'feedback': feedback,
        'total_attendees': total_attendees,
        'avg_rating': avg_rating,
        'today_date': formatted_date,
        'event_dates': event_dates_json,
        'attendee_counts': attendee_counts_json,
        'rating_distribution': rating_distribution_json,
        'speaker_notifications': speaker_notifications,
        'assigned_events': upcoming_assigned_events,
        'speaker': speaker,
    }

    return render(request, 'speaker/dashboard.html', context)

@login_required
def attendee_dashboard(request):
    """
    View function for the attendee dashboard.
    """
    # Get the current user's event registrations
    registrations = Registration.objects.filter(
        user=request.user,
        role__name='attendee'
    ).select_related('event', 'attendee_type')

    # Get upcoming events the user is registered for
    upcoming_events = Event.objects.filter(
        registration__in=registrations,
        start_date__gte=timezone.now()
    ).order_by('start_date')[:5]

    # Get past events the user attended
    past_events = Event.objects.filter(
        registration__in=registrations,
        end_date__lt=timezone.now()
    ).order_by('-end_date')[:5]

    # Get the user's feedback
    feedback = Feedback.objects.filter(
        user=request.user
    ).order_by('-feedback_id')[:5]

    # Get all upcoming events for the recommended section
    # This is a simplified version - in a real app, you'd use more sophisticated recommendation logic
    all_upcoming_events = Event.objects.filter(
        start_date__gte=timezone.now()
    ).order_by('start_date')[:6]

    # Filter out events the user is already registered for
    recommended_events = [event for event in all_upcoming_events if event not in upcoming_events][:3]

    context = {
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'feedback': feedback,
        'recommended_events': recommended_events,
        'user_role': 'Attendee'
    }

    return render(request, 'attendee/dashboard.html', context)


@login_required
def recent_events(request):
    """
    View function for displaying recent events for an attendee.
    Shows only events the user is registered for.
    """
    # Get the current user's event registrations
    registrations = Registration.objects.filter(
        user=request.user,
        role__name='attendee'
    ).select_related('event', 'attendee_type')

    # Get events the user is registered for
    events = Event.objects.filter(
        registration__in=registrations
    ).select_related('category').prefetch_related('tags').order_by('-start_date')

    # Apply search query if provided
    search_query = request.GET.get('q')
    if search_query:
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(tags__name__icontains=search_query)
        ).distinct()

    # Apply time filter if provided
    time_filter = request.GET.get('time')
    if time_filter == 'past':
        events = events.filter(end_date__lt=timezone.now())
    elif time_filter == 'upcoming':
        events = events.filter(start_date__gte=timezone.now())

    # Apply category filter if provided
    category_filter = request.GET.get('category')
    if category_filter:
        events = events.filter(category__name=category_filter)

    # Get all categories for the filter dropdown
    categories = EventCategory.objects.all()

    # Mark events as past, active, or upcoming
    now = timezone.now()
    for event in events:
        event.is_past = event.end_date < now
        event.is_active = event.start_date <= now and event.end_date >= now
        event.registration = registrations.filter(event=event).first()

    # Pagination
    paginator = Paginator(events, 5)  # Show 5 events per page
    page_number = request.GET.get('page')
    events_page = paginator.get_page(page_number)

    context = {
        'events': events_page,
        'categories': categories,
        'filters': {
            'category': category_filter,
            'time': time_filter,
            'q': search_query
        },
        'user_role': 'Attendee'
    }

    return render(request, 'attendee/recent_events.html', context)

@login_required
def browse_events(request):
    """
    View function for browsing all available events.
    Shows all events with advanced filtering options.
    """
    # Get the current user's event registrations for registration status
    registrations = Registration.objects.filter(
        user=request.user,
        role__name='attendee'
    ).select_related('event', 'attendee_type')

    # Get all events
    events = Event.objects.all().select_related('category', 'organizer').prefetch_related('tags').order_by('-start_date')

    # Apply time filter if provided
    time_filter = request.GET.get('time')
    if time_filter == 'past':
        events = events.filter(end_date__lt=timezone.now())
    elif time_filter == 'upcoming':
        events = events.filter(start_date__gte=timezone.now())

    # Apply category filter if provided
    category_filter = request.GET.get('category')
    if category_filter:
        events = events.filter(category__name=category_filter)

    # Apply tag filter if provided
    tag_filter = request.GET.get('tag')
    if tag_filter:
        events = events.filter(tags__name=tag_filter)

    # Apply search query if provided
    search_query = request.GET.get('q')
    if search_query:
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(organizer__email__icontains=search_query) |
            Q(tags__name__icontains=search_query)
        ).distinct()

    # Get all categories and tags for the filter dropdowns
    categories = EventCategory.objects.all()
    tags = EventTag.objects.filter(is_tech=True).order_by('name')

    # Mark events as past, active, or upcoming and add registration info
    now = timezone.now()
    for event in events:
        event.is_past = event.end_date < now
        event.is_active = event.start_date <= now and event.end_date >= now
        event.registration = registrations.filter(event=event).first()

    # Pagination
    paginator = Paginator(events, 6)  # Show 6 events per page for grid layout
    page_number = request.GET.get('page')
    events_page = paginator.get_page(page_number)

    context = {
        'events': events_page,
        'categories': categories,
        'tech_tags': tags,
        'filters': {
            'category': category_filter,
            'tag': tag_filter,
            'time': time_filter,
            'q': search_query
        },
        'user_role': 'Attendee'
    }

    return render(request, 'attendee/browse_events.html', context)

@login_required
def organizer_dashboard(request):
    """
    View function for the organizer dashboard.
    """
    # Add debug logging
    messages.info(request, f"User {request.user.email} accessing organizer dashboard")

    # Check if the user has the organizer role
    has_organizer_role = Registration.objects.filter(
        user=request.user,
        role__name='organizer'
    ).exists()

    if not has_organizer_role:
        messages.warning(request, "You don't have an organizer role. Showing organizer dashboard anyway.")

    # Get events created by the current user
    user_events = Event.objects.filter(organizer=request.user)

    # Get upcoming events
    upcoming_events = user_events.filter(
        start_date__gte=timezone.now()
    ).order_by('start_date')[:5]

    # Get past events
    past_events = user_events.filter(
        end_date__lt=timezone.now()
    ).order_by('-end_date')[:5]

    # Get event statistics
    total_events_count = user_events.count()
    total_attendees_count = Registration.objects.filter(
        event__in=user_events,
        role__name='attendee'
    ).count()
    total_speakers_count = Registration.objects.filter(
        event__in=user_events,
        role__name='speaker'
    ).count()
    total_sponsors_count = Sponsor.objects.filter(
        event__in=user_events
    ).count()

    # Get recent registrations
    recent_registrations = Registration.objects.filter(
        event__in=user_events
    ).select_related('user', 'event', 'role', 'attendee_type').order_by('-registered_at')[:5]

    # Get recent feedback
    recent_feedback = Feedback.objects.filter(
        event__in=user_events
    ).select_related('user', 'event').order_by('-feedback_id')[:5]

    # Prepare chart data
    registration_dates = ['Jan', 'Feb', 'Mar', 'Apr', 'May']
    registration_counts = [5, 10, 15, 20, 25]
    category_labels = ['Conference', 'Workshop', 'Seminar', 'Hackathon', 'Other']
    category_data = [30, 20, 15, 25, 10]

    # Convert data to JSON strings to safely embed in template
    registration_dates_json = json.dumps(registration_dates)
    registration_counts_json = json.dumps(registration_counts)
    category_labels_json = json.dumps(category_labels)
    category_data_json = json.dumps(category_data)

    # Get today's date
    today = timezone.now().date()
    formatted_date = today.strftime('%B %d, %Y')  # Format example: January 01, 2023

    context = {
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'total_events_count': total_events_count,
        'total_attendees_count': total_attendees_count,
        'total_speakers_count': total_speakers_count,
        'total_sponsors_count': total_sponsors_count,
        'recent_registrations': recent_registrations,
        'recent_feedback': recent_feedback,
        'registration_dates': registration_dates_json,
        'registration_counts': registration_counts_json,
        'category_labels': category_labels_json,
        'category_data': category_data_json,
        'today_date': formatted_date,
    }

    return render(request, 'organizer/dashboard.html', context)

# Placeholder views for organizer features
@login_required
def my_events(request):
    """
    View function for displaying events created by the current user (organizer).
    """
    # Get events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # For each event, get the number of attendees
    for event in events:
        event.attendees_count = Registration.objects.filter(event=event).count()

    # Get total statistics
    total_attendees = Registration.objects.filter(event__in=events).count()
    total_speakers = Registration.objects.filter(event__in=events, role__name='speaker').count()
    total_feedback = Feedback.objects.filter(event__in=events).count()

    context = {
        'events': events,
        'total_attendees': total_attendees,
        'total_speakers': total_speakers,
        'total_feedback': total_feedback,
    }

    return render(request, 'my_events.html', context)

@login_required
def create_event(request):
    """
    View function for creating a new event.
    """
    # Ensure the user has the organizer role
    has_organizer_role = Registration.objects.filter(
        user=request.user,
        role__name='organizer'
    ).exists()

    if not has_organizer_role:
        messages.warning(request, "You need an organizer role to create events.")

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            # Create the event but don't save to DB yet
            event = form.save(commit=False)
            # Set the organizer to the current user
            event.organizer = request.user

            # Handle custom registration link
            custom_link = form.cleaned_data.get('custom_registration_link')
            if not custom_link:
                # Clear any manually entered registration link to generate a new one
                event.registration_link = ''

            # Save the event to the database
            event.save()

            # Create a registration for the organizer
            organizer_role = ParticipantRole.objects.get(name='organizer')
            Registration.objects.create(
                event=event,
                user=request.user,
                role=organizer_role
            )

            # Handle speaker assignments
            speakers = form.cleaned_data.get('speakers')
            keynote_speaker = form.cleaned_data.get('keynote_speaker')
            speaker_topics_text = form.cleaned_data.get('speaker_topics', '')
            notify_speakers = form.cleaned_data.get('notify_speakers', True)

            # Parse speaker topics
            speaker_topics = {}
            if speaker_topics_text:
                lines = speaker_topics_text.strip().split('\n')
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        name = parts[0].strip()
                        topic = parts[1].strip()
                        speaker_topics[name] = topic

            # Process each speaker
            if speakers:
                speaker_role = ParticipantRole.objects.get(name='speaker')

                for user in speakers:
                    # Get or create Speaker object
                    speaker, created = Speaker.objects.get_or_create(
                        user=user,
                        defaults={'bio': f"Bio for {user.get_full_name() or user.email}"}
                    )

                    # Determine if this is the keynote speaker
                    is_keynote = (keynote_speaker and user == keynote_speaker)

                    # Find topic for this speaker
                    topic = ""
                    speaker_name = user.get_full_name()
                    if speaker_name in speaker_topics:
                        topic = speaker_topics[speaker_name]

                    # Create EventSpeaker relationship
                    event_speaker = EventSpeaker.objects.create(
                        event=event,
                        speaker=speaker,
                        topic=topic,
                        is_keynote=is_keynote,
                        presentation_time=event.start_date  # Default to event start time
                    )

                    # Create registration for the speaker if it doesn't exist
                    if not Registration.objects.filter(event=event, user=user).exists():
                        Registration.objects.create(
                            event=event,
                            user=user,
                            role=speaker_role
                        )

                    # Send notification to the speaker
                    if notify_speakers:
                        # Create in-app notification
                        create_notification(
                            user=user,
                            event=event,
                            notification_type='speaker_added',
                            title='Speaker Assignment',
                            message=f"You have been assigned as a speaker for '{event.title}'." +
                                    (f" Topic: {topic}" if topic else ""),
                            icon='fa-microphone',
                            color='success',
                            action_url=f"/events/events/{event.event_id}/"
                        )

                        # Send email notification
                        send_speaker_assignment_email(user, event, topic, is_keynote)

            # Create notifications for all users who might be interested
            # Get all users except the organizer
            users = User.objects.exclude(user_id=request.user.user_id)

            # Create a notification for each user
            for user in users:
                # Check if the user has any registrations with the same category
                user_has_similar_events = Registration.objects.filter(
                    user=user,
                    event__category=event.category
                ).exists()

                # Only notify users who have shown interest in this category
                if user_has_similar_events:
                    create_notification(
                        user=user,
                        event=event,
                        notification_type='event_created',
                        title='New Event Created',
                        message=f"A new event '{event.title}' has been created that matches your interests.",
                        icon='fa-calendar-plus',
                        color='primary',
                        action_url=f"/events/events/{event.event_id}/"
                    )

            messages.success(request, f"Event '{event.title}' created successfully!")
            return redirect('event_detail', event_id=event.event_id)
    else:
        form = EventForm()

    # Get existing event categories
    categories = EventCategory.objects.all()
    if not categories.exists():
        # Create some default categories if none exist
        default_categories = [
            'Conference', 'Workshop', 'Seminar', 'Hackathon',
            'Networking', 'Webinar', 'Exhibition', 'Other'
        ]
        for category_name in default_categories:
            EventCategory.objects.create(name=category_name)
        # Refresh the categories
        categories = EventCategory.objects.all()

    context = {
        'form': form,
        'categories': categories,
    }

    return render(request, 'create_event.html', context)

@login_required
def manage_speakers(request):
    """
    View function for managing speakers.
    """
    # Get all speakers
    speakers = Speaker.objects.all().select_related('user')

    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # For each speaker, get their event registrations
    for speaker in speakers:
        speaker.registrations = Registration.objects.filter(
            user=speaker.user,
            role__name='speaker'
        ).select_related('event')

        # Ensure social_links is a dictionary with expected keys
        if not speaker.social_links:
            speaker.social_links = {}

        # Make sure all expected keys exist
        if 'linkedin' not in speaker.social_links:
            speaker.social_links['linkedin'] = ''
        if 'twitter' not in speaker.social_links:
            speaker.social_links['twitter'] = ''
        if 'website' not in speaker.social_links:
            speaker.social_links['website'] = ''

    # Get statistics
    total_events = events.filter(
        registration__role__name='speaker'
    ).distinct().count()

    total_feedback = Feedback.objects.filter(
        event__in=events,
        event__registration__role__name='speaker'
    ).count()

    # Calculate average speaker rating if there's feedback
    avg_rating = 0
    if total_feedback > 0:
        avg_rating = Feedback.objects.filter(
            event__in=events,
            event__registration__role__name='speaker'
        ).aggregate(avg=models.Avg('rating'))['avg'] or 0

    context = {
        'speakers': speakers,
        'events': events,
        'total_events': total_events,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
    }

    return render(request, 'organizer/manage_speakers.html', context)

@login_required
def manage_sponsors(request):
    """
    Enhanced view function for managing sponsors with tiers and profiles.
    """
    # Get all sponsors for the current user's events
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Check if enhanced sponsor system is set up
    from django.db import connection
    new_structure = False
    sponsor_tiers = []
    sponsor_profiles = []

    try:
        with connection.cursor() as cursor:
            # Check if enhanced tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_sponsortier'")
            tier_table_exists = cursor.fetchone() is not None

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events_sponsorprofile'")
            profile_table_exists = cursor.fetchone() is not None

            if tier_table_exists and profile_table_exists:
                # Enhanced structure exists
                new_structure = True

                # Get sponsor tiers
                cursor.execute("SELECT * FROM events_sponsortier ORDER BY display_order")
                tier_rows = cursor.fetchall()
                sponsor_tiers = []
                for row in tier_rows:
                    sponsor_tiers.append({
                        'tier_id': row[0],
                        'name': row[1],
                        'display_order': row[2],
                        'color_code': row[3],
                        'base_price': row[4],
                        'logo_placement': row[5],
                        'booth_space': row[6],
                        'speaking_opportunities': row[7],
                        'networking_access': row[8],
                        'marketing_materials': row[9],
                        'social_media_mentions': row[10],
                        'email_mentions': row[11],
                    })

                # Get sponsor profiles
                cursor.execute("SELECT * FROM events_sponsorprofile WHERE is_active = 1 ORDER BY company_name")
                profile_rows = cursor.fetchall()
                sponsor_profiles = []
                for row in profile_rows:
                    sponsor_profiles.append({
                        'profile_id': row[0],
                        'company_name': row[1],
                        'company_description': row[2],
                        'website': row[3],
                        'industry': row[4],
                        'company_size': row[5],
                        'primary_contact_name': row[6],
                        'primary_contact_email': row[7],
                        'primary_contact_phone': row[8],
                        'primary_contact_title': row[9],
                    })

                # Get enhanced sponsors with profile and tier information using Django ORM
                try:
                    print(f"Fetching sponsors for user: {request.user.user_id}")

                    # Use Django ORM to avoid string formatting issues
                    from events.models import Sponsor, SponsorProfile, SponsorTier

                    enhanced_sponsors = Sponsor.objects.filter(
                        event__organizer=request.user
                    ).select_related(
                        'sponsor_profile', 'tier', 'event'
                    ).order_by('-event__start_date', 'tier__display_order')

                    sponsors_data = []
                    for sponsor in enhanced_sponsors:
                        sponsors_data.append({
                            'sponsor_id': str(sponsor.sponsor_id),
                            'event_id': str(sponsor.event.event_id),
                            'sponsor_profile_id': str(sponsor.sponsor_profile.profile_id) if sponsor.sponsor_profile else None,
                            'tier_id': str(sponsor.tier.tier_id) if sponsor.tier else None,
                            'sponsorship_amount': float(sponsor.sponsorship_amount) if sponsor.sponsorship_amount else 0.0,
                            'contract_signed': sponsor.contract_signed,
                            'payment_received': sponsor.payment_received,
                            'status': sponsor.status,
                            'company_name': sponsor.sponsor_profile.company_name if sponsor.sponsor_profile else 'Unknown Company',
                            'industry': sponsor.sponsor_profile.industry if sponsor.sponsor_profile else '',
                            'website': sponsor.sponsor_profile.website if sponsor.sponsor_profile else '',
                            'tier_name': sponsor.tier.name if sponsor.tier else 'No Tier',
                            'tier_color': sponsor.tier.color_code if sponsor.tier else '#000000',
                            'tier_base_price': float(sponsor.tier.base_price) if sponsor.tier else 0.0,
                            'event_title': sponsor.event.title,
                            'event_start_date': sponsor.event.start_date,
                        })

                    # Override sponsors with enhanced data
                    sponsors = sponsors_data
                    print(f"Found {len(sponsors_data)} enhanced sponsors")
                except Exception as e:
                    print("Error fetching enhanced sponsors:", str(e))
                    print("Full error details:", str(e))
                    print("Error type:", type(e))
                    import traceback
                    print("Traceback:", traceback.format_exc())
                    sponsors = []
            else:
                # No enhanced structure, use basic sponsors
                sponsors = Sponsor.objects.filter(event__in=events).select_related('event')
                if sponsors.exists():
                    sponsors = sponsors.order_by('name')

    except Exception as e:
        # If there's any error, use basic structure
        sponsors = Sponsor.objects.filter(event__in=events).select_related('event')
        if sponsors.exists():
            first_sponsor = sponsors.first()
            if hasattr(first_sponsor, 'name'):
                sponsors = sponsors.order_by('name')
            else:
                sponsors = sponsors.order_by('sponsor_id')

    # Handle form submissions only if new structure exists
    if request.method == 'POST' and new_structure:
        action = request.POST.get('action')

        if action == 'create_sponsor_tier':
            # Handle tier creation with raw SQL
            try:
                import uuid
                from django.db import connection

                tier_id = str(uuid.uuid4())
                name = request.POST.get('name')
                display_order = int(request.POST.get('display_order', 0))
                color_code = request.POST.get('color_code', '#000000')
                base_price = float(request.POST.get('base_price', 0))
                logo_placement = request.POST.get('logo_placement', '')
                booth_space = request.POST.get('booth_space', '')
                speaking_opportunities = 1 if request.POST.get('speaking_opportunities') else 0
                networking_access = 1 if request.POST.get('networking_access') else 0
                marketing_materials = 1 if request.POST.get('marketing_materials') else 0
                social_media_mentions = int(request.POST.get('social_media_mentions', 0))
                email_mentions = int(request.POST.get('email_mentions', 0))

                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO events_sponsortier (
                            tier_id, name, display_order, color_code, base_price,
                            logo_placement, booth_space, speaking_opportunities,
                            networking_access, marketing_materials, social_media_mentions,
                            email_mentions, additional_benefits, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, [
                        tier_id, name, display_order, color_code, base_price,
                        logo_placement, booth_space, speaking_opportunities,
                        networking_access, marketing_materials, social_media_mentions,
                        email_mentions, '[]'
                    ])

                messages.success(request, f"Sponsor tier '{name}' created successfully.")
                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error creating sponsor tier: {str(e)}")

        elif action == 'create_sponsor_profile':
            try:
                # Create sponsor profile using Django's ORM
                sponsor_profile = SponsorProfile.objects.create(
                    company_name=request.POST.get('company_name'),
                    company_description=request.POST.get('company_description', ''),
                    website=request.POST.get('website', ''),
                    industry=request.POST.get('industry', ''),
                    company_size=request.POST.get('company_size', ''),
                    primary_contact_name=request.POST.get('primary_contact_name'),
                    primary_contact_email=request.POST.get('primary_contact_email'),
                    primary_contact_phone=request.POST.get('primary_contact_phone', ''),
                    primary_contact_title=request.POST.get('primary_contact_title', ''),
                    address_line1=request.POST.get('address_line1', ''),
                    address_line2=request.POST.get('address_line2', ''),
                    city=request.POST.get('city', ''),
                    state_province=request.POST.get('state_province', ''),
                    postal_code=request.POST.get('postal_code', ''),
                    country=request.POST.get('country', ''),
                    is_active=True
                )

                # Handle file uploads if present
                if 'logo' in request.FILES:
                    sponsor_profile.logo = request.FILES['logo']
                if 'banner_image' in request.FILES:
                    sponsor_profile.banner_image = request.FILES['banner_image']
                if 'marketing_materials' in request.FILES:
                    sponsor_profile.marketing_materials = request.FILES['marketing_materials']
                
                sponsor_profile.save()

                messages.success(request, f"Company profile '{sponsor_profile.company_name}' created successfully.")
                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error creating company profile: {str(e)}")
                return redirect('manage_sponsors')

        elif action == 'edit_sponsor_tier':
            # Handle tier editing with raw SQL
            try:
                from django.db import connection

                tier_id = request.POST.get('tier_id')
                name = request.POST.get('name')
                display_order = int(request.POST.get('display_order', 0))
                color_code = request.POST.get('color_code', '#000000')
                base_price = float(request.POST.get('base_price', 0))
                logo_placement = request.POST.get('logo_placement', '')
                booth_space = request.POST.get('booth_space', '')
                speaking_opportunities = 1 if request.POST.get('speaking_opportunities') else 0
                networking_access = 1 if request.POST.get('networking_access') else 0
                marketing_materials = 1 if request.POST.get('marketing_materials') else 0
                social_media_mentions = int(request.POST.get('social_media_mentions', 0))
                email_mentions = int(request.POST.get('email_mentions', 0))

                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE events_sponsortier SET
                            name = ?, display_order = ?, color_code = ?, base_price = ?,
                            logo_placement = ?, booth_space = ?, speaking_opportunities = ?,
                            networking_access = ?, marketing_materials = ?, social_media_mentions = ?,
                            email_mentions = ?, updated_at = datetime('now')
                        WHERE tier_id = ?
                    """, [
                        name, display_order, color_code, base_price,
                        logo_placement, booth_space, speaking_opportunities,
                        networking_access, marketing_materials, social_media_mentions,
                        email_mentions, tier_id
                    ])

                messages.success(request, f"Sponsor tier '{name}' updated successfully.")
                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error updating sponsor tier: {str(e)}")

        elif action == 'edit_sponsor_profile':
            # Handle profile editing with raw SQL
            try:
                from django.db import connection

                profile_id = request.POST.get('profile_id')
                company_name = request.POST.get('company_name')
                company_description = request.POST.get('company_description', '')
                website = request.POST.get('website', '')
                industry = request.POST.get('industry', '')
                company_size = request.POST.get('company_size', '')
                primary_contact_name = request.POST.get('primary_contact_name')
                primary_contact_email = request.POST.get('primary_contact_email')
                primary_contact_phone = request.POST.get('primary_contact_phone', '')
                primary_contact_title = request.POST.get('primary_contact_title', '')

                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE events_sponsorprofile SET
                            company_name = ?, company_description = ?, website = ?, industry = ?,
                            company_size = ?, primary_contact_name = ?, primary_contact_email = ?,
                            primary_contact_phone = ?, primary_contact_title = ?, updated_at = datetime('now')
                        WHERE profile_id = ?
                    """, [
                        company_name, company_description, website, industry,
                        company_size, primary_contact_name, primary_contact_email,
                        primary_contact_phone, primary_contact_title, profile_id
                    ])

                messages.success(request, f"Company profile '{company_name}' updated successfully.")
                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error updating company profile: {str(e)}")

        elif action == 'delete_sponsor_tier':
            # Handle tier deletion
            try:
                from django.db import connection

                tier_id = request.POST.get('tier_id')

                with connection.cursor() as cursor:
                    # Check if tier is being used by any sponsors
                    cursor.execute("SELECT COUNT(*) FROM events_sponsor WHERE tier_id = ?", [tier_id])
                    sponsor_count = cursor.fetchone()[0]

                    if sponsor_count > 0:
                        messages.error(request, f"Cannot delete tier. It is being used by {sponsor_count} sponsor(s).")
                    else:
                        # Get tier name for message
                        cursor.execute("SELECT name FROM events_sponsortier WHERE tier_id = ?", [tier_id])
                        tier_name = cursor.fetchone()[0]

                        # Delete the tier
                        cursor.execute("DELETE FROM events_sponsortier WHERE tier_id = ?", [tier_id])
                        messages.success(request, f"Sponsor tier '{tier_name}' deleted successfully.")

                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error deleting sponsor tier: {str(e)}")

        elif action == 'delete_sponsor_profile':
            # Handle profile deletion
            try:
                from django.db import connection

                profile_id = request.POST.get('profile_id')

                with connection.cursor() as cursor:
                    # Check if profile is being used by any sponsors
                    cursor.execute("SELECT COUNT(*) FROM events_sponsor WHERE sponsor_profile_id = ?", [profile_id])
                    sponsor_count = cursor.fetchone()[0]

                    if sponsor_count > 0:
                        messages.error(request, f"Cannot delete company profile. It is being used by {sponsor_count} sponsor(s).")
                    else:
                        # Get company name for message
                        cursor.execute("SELECT company_name FROM events_sponsorprofile WHERE profile_id = ?", [profile_id])
                        company_name = cursor.fetchone()[0]

                        # Delete the profile
                        cursor.execute("DELETE FROM events_sponsorprofile WHERE profile_id = ?", [profile_id])
                        messages.success(request, f"Company profile '{company_name}' deleted successfully.")

                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error deleting company profile: {str(e)}")

        elif action == 'add_event_sponsor':
            try:
                event_id = request.POST.get('event_id')
                profile_id = request.POST.get('profile_id')
                tier_id = request.POST.get('tier_id')
                sponsorship_amount = request.POST.get('sponsorship_amount', 0)
                contract_signed = bool(request.POST.get('contract_signed'))
                payment_received = bool(request.POST.get('payment_received'))
                status = request.POST.get('status', 'pending')

                # Get the required objects
                event = Event.objects.get(event_id=event_id, organizer=request.user)
                sponsor_profile = SponsorProfile.objects.get(profile_id=profile_id)
                tier = SponsorTier.objects.get(tier_id=tier_id)

                # Check if this company is already sponsoring this event
                if Sponsor.objects.filter(event=event, sponsor_profile=sponsor_profile).exists():
                    messages.error(request, "This company is already sponsoring this event.")
                    return redirect('manage_sponsors')

                # Create the sponsor
                sponsor = Sponsor.objects.create(
                    event=event,
                    sponsor_profile=sponsor_profile,
                    tier=tier,
                    sponsorship_amount=sponsorship_amount,
                    contract_signed=contract_signed,
                    payment_received=payment_received,
                    status=status
                )

                # Send confirmation email
                if send_sponsor_confirmation_email(sponsor, request):
                    messages.success(request, f"Added {sponsor_profile.company_name} as a {tier.name} sponsor for {event.title}. Confirmation email sent.")
                else:
                    messages.warning(request, f"Added {sponsor_profile.company_name} as a {tier.name} sponsor for {event.title}, but failed to send confirmation email.")

                return redirect('manage_sponsors')

            except Event.DoesNotExist:
                messages.error(request, "Event not found.")
            except SponsorProfile.DoesNotExist:
                messages.error(request, "Company profile not found.")
            except SponsorTier.DoesNotExist:
                messages.error(request, "Sponsor tier not found.")
            except Exception as e:
                messages.error(request, f"Error adding event sponsor: {str(e)}")

        elif action == 'remove_event_sponsor':
            # Handle removing sponsor from event
            try:
                from django.db import connection

                sponsor_id = request.POST.get('sponsor_id')

                with connection.cursor() as cursor:
                    # Get sponsor details for message
                    cursor.execute("""
                        SELECT sp.company_name, e.title
                        FROM events_sponsor s
                        JOIN events_sponsorprofile sp ON s.sponsor_profile_id = sp.profile_id
                        JOIN events_event e ON s.event_id = e.event_id
                        WHERE s.sponsor_id = ?
                    """, [sponsor_id])

                    result = cursor.fetchone()
                    if result:
                        company_name, event_title = result

                        # Delete the sponsor relationship
                        cursor.execute("DELETE FROM events_sponsor WHERE sponsor_id = ?", [sponsor_id])
                        messages.success(request, f"Removed {company_name} as sponsor from {event_title}.")
                    else:
                        messages.error(request, "Sponsor relationship not found.")

                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error removing event sponsor: {str(e)}")

        elif action == 'edit_event_sponsor':
            # Handle editing event sponsor
            try:
                from django.db import connection

                sponsor_id = request.POST.get('sponsor_id')
                profile_id = request.POST.get('profile_id')
                tier_id = request.POST.get('tier_id')
                sponsorship_amount = float(request.POST.get('sponsorship_amount', 0))
                contract_signed = 1 if request.POST.get('contract_signed') else 0
                payment_received = 1 if request.POST.get('payment_received') else 0
                status = request.POST.get('status', 'pending')

                with connection.cursor() as cursor:
                    # Get company and tier names for message
                    cursor.execute("SELECT company_name FROM events_sponsorprofile WHERE profile_id = ?", [profile_id])
                    company_name = cursor.fetchone()[0]

                    cursor.execute("SELECT name FROM events_sponsortier WHERE tier_id = ?", [tier_id])
                    tier_name = cursor.fetchone()[0]

                    # Update sponsor relationship
                    cursor.execute("""
                        UPDATE events_sponsor SET
                            sponsor_profile_id = ?, tier_id = ?, sponsorship_amount = ?,
                            contract_signed = ?, payment_received = ?, status = ?,
                            updated_at = datetime('now')
                        WHERE sponsor_id = ?
                    """, [
                        profile_id, tier_id, sponsorship_amount,
                        contract_signed, payment_received, status, sponsor_id
                    ])

                messages.success(request, f"Successfully updated {company_name} sponsorship details!")
                return redirect('manage_sponsors')

            except Exception as e:
                messages.error(request, f"Error updating event sponsor: {str(e)}")

        elif action == 'create_event_sponsor':
            try:
                event_id = request.POST.get('event_id')
                profile_id = request.POST.get('profile_id')
                tier_id = request.POST.get('tier_id')
                sponsorship_amount = request.POST.get('sponsorship_amount', 0)

                # Get the required objects
                event = Event.objects.get(event_id=event_id)
                sponsor_profile = SponsorProfile.objects.get(profile_id=profile_id)
                tier = SponsorTier.objects.get(tier_id=tier_id)

                # Check if this company is already sponsoring this event
                if Sponsor.objects.filter(event=event, sponsor_profile=sponsor_profile).exists():
                    messages.error(request, "This company is already sponsoring this event.")
                    return redirect('manage_sponsors')

                # Create the sponsor
                sponsor = Sponsor.objects.create(
                    event=event,
                    sponsor_profile=sponsor_profile,
                    tier=tier,
                    sponsorship_amount=sponsorship_amount,
                    status='pending'
                )

                messages.success(request, f"Added {sponsor_profile.company_name} as a {tier.name} sponsor for {event.title}.")
                return redirect('manage_sponsors')

            except Event.DoesNotExist:
                messages.error(request, "Event not found.")
            except SponsorProfile.DoesNotExist:
                messages.error(request, "Company profile not found.")
            except SponsorTier.DoesNotExist:
                messages.error(request, "Sponsor tier not found.")
            except Exception as e:
                messages.error(request, f"Error adding event sponsor: {str(e)}")
            return redirect('manage_sponsors')

    # Create empty form data for templates
    sponsor_profile_form = None
    sponsor_tier_form = None
    sponsor_form = None

    # Get statistics
    if isinstance(sponsors, list):
        total_sponsors = len(sponsors)
    else:
        total_sponsors = sponsors.count() if hasattr(sponsors, 'count') else 0

    total_profiles = len(sponsor_profiles) if new_structure else 0
    total_tiers = len(sponsor_tiers) if new_structure else 0

    # Count sponsors by tier and calculate statistics
    tier_stats = {
        'gold': 0,
        'silver': 0,
        'bronze': 0,
    }

    total_revenue = 0
    recent_sponsors = []

    # Handle statistics based on data type
    if new_structure and isinstance(sponsors, list):
        # Enhanced structure with list data
        total_revenue = sum(float(sponsor.get('sponsorship_amount', 0) or 0) for sponsor in sponsors)
        recent_sponsors = sponsors[:5]

        # Count by tier
        tier_counts = {}
        for sponsor in sponsors:
            tier_name = sponsor.get('tier_name', '').lower()
            if tier_name:
                tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        tier_stats.update(tier_counts)

    else:
        # Basic structure with QuerySet
        try:
            if hasattr(sponsors, 'exists') and sponsors.exists():
                first_sponsor = sponsors.first()
                if hasattr(first_sponsor, 'tier'):
                    tier_stats = {
                        'gold': sponsors.filter(tier='gold').count(),
                        'silver': sponsors.filter(tier='silver').count(),
                        'bronze': sponsors.filter(tier='bronze').count(),
                    }
                recent_sponsors = list(sponsors[:5])
        except:
            pass

    context = {
        'sponsors': sponsors,
        'events': events,
        'sponsor_tiers': sponsor_tiers,
        'sponsor_profiles': sponsor_profiles,
        'sponsor_profile_form': sponsor_profile_form,
        'sponsor_tier_form': sponsor_tier_form,
        'sponsor_form': sponsor_form,
        'total_sponsors': total_sponsors,
        'total_profiles': total_profiles,
        'total_tiers': total_tiers,
        'tier_stats': tier_stats,
        'total_revenue': total_revenue,
        'recent_sponsors': recent_sponsors,
        'new_structure': new_structure,
    }

    # Always use the enhanced template since it handles both structures
    return render(request, 'manage_sponsors_enhanced.html', context)


@login_required
def setup_enhanced_sponsors_view(request):
    """
    Set up enhanced sponsor management system
    """
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('manage_sponsors')

    from django.db import connection

    try:
        with connection.cursor() as cursor:
            # Create SponsorTier table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events_sponsortier (
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
                    additional_benefits TEXT DEFAULT '[]',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create SponsorProfile table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events_sponsorprofile (
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
                    social_media_links TEXT DEFAULT '{}',
                    marketing_materials VARCHAR(100),
                    notes TEXT,
                    special_requirements TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Check current sponsor table structure and add missing columns
            cursor.execute("PRAGMA table_info(events_sponsor)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add missing columns to sponsor table
            if 'sponsor_profile_id' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN sponsor_profile_id TEXT")

            if 'tier_id' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN tier_id TEXT")

            if 'sponsorship_amount' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN sponsorship_amount DECIMAL(10, 2) DEFAULT 0.00")

            if 'contract_signed' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN contract_signed BOOLEAN DEFAULT 0")

            if 'contract_date' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN contract_date DATE")

            if 'payment_received' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN payment_received BOOLEAN DEFAULT 0")

            if 'payment_date' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN payment_date DATE")

            if 'custom_benefits' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN custom_benefits TEXT DEFAULT '[]'")

            if 'status' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")

            if 'created_at' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

            if 'updated_at' not in columns:
                cursor.execute("ALTER TABLE events_sponsor ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")

        # Create default sponsor tiers
        create_default_tiers()

        messages.success(request, "Enhanced sponsor management system has been set up successfully!")

    except Exception as e:
        messages.error(request, f"Error setting up enhanced sponsor system: {str(e)}")

    return redirect('manage_sponsors')


def create_default_tiers():
    """Create default sponsor tiers using raw SQL"""
    from django.db import connection
    import uuid

    default_tiers = [
        {
            'name': 'Platinum',
            'display_order': 1,
            'color_code': '#E5E4E2',
            'base_price': 750000.00,  # ₹7,50,000
            'logo_placement': 'Main stage backdrop, Website header, All marketing materials',
            'booth_space': 'Premium 20x20 booth in prime location',
            'speaking_opportunities': 1,
            'networking_access': 1,
            'marketing_materials': 1,
            'social_media_mentions': 10,
            'email_mentions': 5,
        },
        {
            'name': 'Gold',
            'display_order': 2,
            'color_code': '#FFD700',
            'base_price': 500000.00,  # ₹5,00,000
            'logo_placement': 'Stage backdrop, Website, Event programs',
            'booth_space': 'Standard 15x15 booth in high-traffic area',
            'speaking_opportunities': 1,
            'networking_access': 1,
            'marketing_materials': 1,
            'social_media_mentions': 7,
            'email_mentions': 3,
        },
        {
            'name': 'Silver',
            'display_order': 3,
            'color_code': '#C0C0C0',
            'base_price': 300000.00,  # ₹3,00,000
            'logo_placement': 'Website, Event programs, Registration area',
            'booth_space': 'Standard 10x10 booth',
            'speaking_opportunities': 0,
            'networking_access': 1,
            'marketing_materials': 1,
            'social_media_mentions': 5,
            'email_mentions': 2,
        },
        {
            'name': 'Bronze',
            'display_order': 4,
            'color_code': '#CD7F32',
            'base_price': 150000.00,  # ₹1,50,000
            'logo_placement': 'Website, Event programs',
            'booth_space': 'Standard 8x8 booth',
            'speaking_opportunities': 0,
            'networking_access': 0,
            'marketing_materials': 0,
            'social_media_mentions': 2,
            'email_mentions': 1,
        },
    ]

    with connection.cursor() as cursor:
        for tier_data in default_tiers:
            # Check if tier already exists
            cursor.execute("SELECT COUNT(*) FROM events_sponsortier WHERE name = ?", [tier_data['name']])
            if cursor.fetchone()[0] == 0:
                # Insert new tier
                tier_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO events_sponsortier (
                        tier_id, name, display_order, color_code, base_price,
                        logo_placement, booth_space, speaking_opportunities,
                        networking_access, marketing_materials, social_media_mentions,
                        email_mentions, additional_benefits, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """, [
                    tier_id, tier_data['name'], tier_data['display_order'],
                    tier_data['color_code'], tier_data['base_price'],
                    tier_data['logo_placement'], tier_data['booth_space'],
                    tier_data['speaking_opportunities'], tier_data['networking_access'],
                    tier_data['marketing_materials'], tier_data['social_media_mentions'],
                    tier_data['email_mentions'], '[]'
                ])


@login_required
def create_default_sponsor_tiers(request):
    """
    Create default sponsor tiers if they don't exist
    """
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('manage_sponsors')

    # Define default tiers
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

    if created_count > 0:
        messages.success(request, f'Successfully created {created_count} default sponsor tiers!')
    else:
        messages.info(request, 'All default sponsor tiers already exist.')

    return redirect('manage_sponsors')


@login_required
def speaker_schedule(request):
    """
    View function for the speaker's schedule page.
    """
    # Get the current user's events where they are a speaker
    speaker_events = Event.objects.filter(
        registration__user=request.user,
        registration__role__name='speaker'
    ).distinct()

    # Handle calendar export
    if 'export' in request.GET:
        export_format = request.GET.get('export')
        if export_format == 'ical':
            # Create iCal calendar
            cal = Calendar()
            cal.add('prodid', '-//CorpEventX//Speaker Schedule//EN')
            cal.add('version', '2.0')
            cal.add('x-wr-calname', 'Speaking Schedule')

            # Add events to calendar
            for event in speaker_events:
                cal_event = ICalEvent()
                cal_event.add('summary', event.title)
                cal_event.add('description', event.description)
                cal_event.add('location', event.location)
                cal_event.add('dtstart', event.start_date)
                cal_event.add('dtend', event.end_date)
                cal_event.add('dtstamp', datetime.now(pytz.UTC))
                cal_event.add('uid', f'{event.event_id}@corpeventx.com')
                cal.add_component(cal_event)

            # Create response
            response = HttpResponse(cal.to_ical(), content_type='text/calendar')
            response['Content-Disposition'] = 'attachment; filename="speaking_schedule.ics"'
            return response

    # Get filter parameters
    category_filter = request.GET.get('category')
    time_filter = request.GET.get('time', 'all')  # Default to 'all'
    view_type = request.GET.get('view', 'list')  # Default to 'list' view

    # Apply category filter if provided
    if category_filter:
        speaker_events = speaker_events.filter(category__name=category_filter)

    # Get all events initially
    all_events = speaker_events

    # Apply time filter
    now = timezone.now()
    if time_filter == 'upcoming':
        filtered_events = speaker_events.filter(start_date__gte=now).order_by('start_date')
    elif time_filter == 'past':
        filtered_events = speaker_events.filter(end_date__lt=now).order_by('-end_date')
    elif time_filter == 'month':
        # Events in the next 30 days
        thirty_days_later = now + timezone.timedelta(days=30)
        filtered_events = speaker_events.filter(start_date__gte=now, start_date__lte=thirty_days_later).order_by('start_date')
    elif time_filter == 'week':
        # Events in the next 7 days
        seven_days_later = now + timezone.timedelta(days=7)
        filtered_events = speaker_events.filter(start_date__gte=now, start_date__lte=seven_days_later).order_by('start_date')
    else:  # 'all' or any other value
        filtered_events = speaker_events.order_by('start_date')

    # Get upcoming events for the sidebar and main display
    upcoming_events = speaker_events.filter(start_date__gte=now).order_by('start_date')

    # Get past events for the past tab
    past_events = speaker_events.filter(end_date__lt=now).order_by('-end_date')

    # Get all categories for filter dropdown with event counts
    categories = []
    for category in EventCategory.objects.filter(event__in=speaker_events).distinct():
        # Count events in this category
        event_count = filtered_events.filter(category=category).count()
        # Add count attribute to category object
        category.event_count = event_count
        categories.append(category)

    # Get today's date
    today = now.date()
    formatted_date = today.strftime('%B %d, %Y')  # Format example: January 01, 2023

    # Prepare calendar data (events grouped by month and day)
    calendar_events = {}
    for event in upcoming_events:
        month_key = event.start_date.strftime('%B %Y')
        if month_key not in calendar_events:
            calendar_events[month_key] = {}

        day_key = event.start_date.day
        if day_key not in calendar_events[month_key]:
            calendar_events[month_key][day_key] = []

        calendar_events[month_key][day_key].append(event)

    # Calculate statistics
    total_events = speaker_events.count()
    total_upcoming = upcoming_events.count()
    total_past = past_events.count()

    # Calculate total attendees and feedback statistics
    total_attendees = 0
    total_feedback = 0
    total_rating = 0
    feedback_count = 0

    for event in speaker_events:
        # Count attendees
        event_attendees = Registration.objects.filter(event=event).count()
        total_attendees += event_attendees

        # Count feedback and calculate average rating
        event_feedback = event.feedback_set.all()
        total_feedback += event_feedback.count()
        
        for feedback in event_feedback:
            if feedback.rating:
                total_rating += feedback.rating
                feedback_count += 1

    # Calculate average rating
    avg_rating = None
    if feedback_count > 0:
        avg_rating = round(total_rating / feedback_count, 1)

    # Calculate average attendees per event
    avg_attendees = 0
    if total_events > 0:
        avg_attendees = total_attendees / total_events

    # Get event dates and attendee counts for chart
    event_dates = []
    attendee_counts = []

    for event in speaker_events.order_by('start_date'):
        event_dates.append(event.start_date.strftime('%b %d'))
        attendee_counts.append(Registration.objects.filter(event=event).count())

    # Convert data to JSON for JavaScript charts
    import json
    event_dates_json = json.dumps(event_dates)
    attendee_counts_json = json.dumps(attendee_counts)

    context = {
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'filtered_events': filtered_events,
        'calendar_events': calendar_events,
        'categories': categories,
        'today_date': formatted_date,
        'category_filter': category_filter,
        'time_filter': time_filter,
        'view_type': view_type,
        'total_events': total_events,
        'total_upcoming': total_upcoming,
        'total_past': total_past,
        'total_attendees': total_attendees,
        'avg_attendees': avg_attendees,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
        'event_dates': event_dates_json,
        'attendee_counts': attendee_counts_json,
        'now': now,  # Add the current datetime for template comparisons
    }

    return render(request, 'speaker/schedule.html', context)


@login_required
def speaker_materials(request):
    """
    View function for the speaker's presentation materials page.
    """
    # Get the current user's speaker profile
    try:
        speaker = Speaker.objects.get(user=request.user)
    except Speaker.DoesNotExist:
        # Create a speaker profile if it doesn't exist
        speaker = Speaker.objects.create(
            user=request.user,
            bio=f"Bio for {request.user.get_full_name() or request.user.email}"
        )

    # Get the current user's events where they are a speaker
    speaker_events = Event.objects.filter(
        registration__user=request.user,
        registration__role__name='speaker'
    ).distinct()

    # Get upcoming events where the user is a speaker
    upcoming_events = speaker_events.filter(
        start_date__gte=timezone.now()
    ).order_by('start_date')

    # Get all events where the user is a speaker (for displaying materials)
    all_speaker_events = speaker_events.order_by('-start_date')

    # Handle form submission
    if request.method == 'POST' and request.FILES.get('materialFile'):
        event_id = request.POST.get('eventSelect')
        material_type = request.POST.get('materialType')
        material_title = request.POST.get('materialTitle')
        material_description = request.POST.get('materialDescription', '')
        share_with_attendees = request.POST.get('shareWithAttendees') == 'on'

        try:
            # Get the event
            event = Event.objects.get(event_id=event_id)

            # Save the material
            speaker.materials = request.FILES['materialFile']
            speaker.save()

            # Create or update the EventSpeaker relationship
            event_speaker, created = EventSpeaker.objects.get_or_create(
                event=event,
                speaker=speaker,
                defaults={
                    'topic': material_title,
                    'presentation_time': event.start_date
                }
            )

            if not created:
                event_speaker.topic = material_title
                event_speaker.save()

            # Notify the event organizer
            if event.organizer:
                # Create in-app notification for the organizer
                create_notification(
                    user=event.organizer,
                    event=event,
                    notification_type='material_uploaded',
                    title='Presentation Material Uploaded',
                    message=f"{request.user.get_full_name() or request.user.email} has uploaded presentation materials for '{event.title}'.",
                    icon='fa-file-upload',
                    color='success',
                    action_url=f"/events/events/{event.event_id}/"
                )

                # Send email notification to the organizer
                subject = f'Presentation Material Uploaded for {event.title}'
                context = {
                    'organizer': event.organizer,
                    'speaker': request.user,
                    'event': event,
                    'material_title': material_title,
                    'upload_date': timezone.now().strftime('%B %d, %Y'),
                    'event_url': f'/events/events/{event.event_id}/'
                }

                html_message = render_to_string('emails/material_uploaded.html', context)
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [event.organizer.email],
                        html_message=html_message,
                        fail_silently=False
                    )
                except Exception as e:
                    # Log the error but don't stop the process
                    print(f"Error sending email: {str(e)}")

            messages.success(request, f"Material '{material_title}' uploaded successfully for event '{event.title}'")

        except Event.DoesNotExist:
            messages.error(request, "Selected event does not exist.")
        except Exception as e:
            messages.error(request, f"Error uploading material: {str(e)}")

    # Get all materials for this speaker
    speaker_materials = []
    if speaker.materials:
        # Get file info
        file_name = speaker.materials.name.split('/')[-1]
        file_size = speaker.materials.size
        file_type = file_name.split('.')[-1].upper()

        # Determine file type icon and color
        icon_class = "fas fa-file"
        bg_color = "primary"

        if file_type in ['PDF']:
            icon_class = "fas fa-file-pdf"
            bg_color = "danger"
        elif file_type in ['PPTX', 'PPT']:
            icon_class = "fas fa-file-powerpoint"
            bg_color = "primary"
        elif file_type in ['DOCX', 'DOC']:
            icon_class = "fas fa-file-word"
            bg_color = "info"
        elif file_type in ['MP4', 'MOV', 'AVI']:
            icon_class = "fas fa-file-video"
            bg_color = "warning"
        elif file_type in ['ZIP', 'RAR']:
            icon_class = "fas fa-file-archive"
            bg_color = "secondary"

        # Format file size
        if file_size < 1024:
            formatted_size = f"{file_size} B"
        elif file_size < 1024 * 1024:
            formatted_size = f"{file_size/1024:.1f} KB"
        else:
            formatted_size = f"{file_size/(1024*1024):.1f} MB"

        # Add to materials list
        speaker_materials.append({
            'file_name': file_name,
            'file_size': formatted_size,
            'file_type': file_type,
            'icon_class': icon_class,
            'bg_color': bg_color,
            'upload_date': timezone.now().strftime('%b %d, %Y'),
            'url': speaker.materials.url if speaker.materials else None,
        })

    context = {
        'upcoming_events': upcoming_events,
        'all_speaker_events': all_speaker_events,
        'speaker': speaker,
        'speaker_materials': speaker_materials,
    }

    return render(request, 'speaker/materials.html', context)


@login_required
def speaker_guidelines(request):
    """
    View function for the speaker guidelines page.
    """
    return render(request, 'speaker/guidelines.html')


@login_required
def speaker_feedback(request):
    """
    View function for the speaker's feedback page.
    """
    # Get the current user's events where they are a speaker
    speaker_events = Event.objects.filter(
        registration__user=request.user,
        registration__role__name='speaker'
    ).distinct()

    # Get feedback for the user's speaking engagements
    feedback = Feedback.objects.filter(
        event__in=speaker_events
    ).order_by('-feedback_id')

    # Calculate average rating
    avg_rating = 0
    if feedback.exists():
        total_rating = sum(item.rating for item in feedback)
        avg_rating = total_rating / feedback.count()

    # Count events with feedback
    events_with_feedback = speaker_events.filter(
        feedback__isnull=False
    ).distinct().count()

    # Calculate positive feedback percentage (ratings 4-5)
    positive_feedback = feedback.filter(rating__gte=4).count()
    positive_feedback_percentage = 0
    if feedback.count() > 0:
        positive_feedback_percentage = int((positive_feedback / feedback.count()) * 100)

    # Pagination
    paginator = Paginator(feedback, 10)  # Show 10 feedback items per page
    page_number = request.GET.get('page')
    feedback_page = paginator.get_page(page_number)

    context = {
        'feedback': feedback_page,
        'events': speaker_events,
        'total_feedback': feedback.count(),
        'avg_rating': avg_rating,
        'events_with_feedback': events_with_feedback,
        'positive_feedback_percentage': positive_feedback_percentage,
    }

    return render(request, 'speaker/feedback.html', context)

@login_required
def reports(request):
    """
    View function for the analytics and reports page.
    """
    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Get event statistics
    total_events = events.count()

    # Get attendee statistics
    total_attendees = Registration.objects.filter(event__in=events, role__name='attendee').count()

    # Get speaker statistics
    total_speakers = Registration.objects.filter(event__in=events, role__name='speaker').count()

    # Get feedback statistics
    total_feedback = Feedback.objects.filter(event__in=events).count()

    # Calculate average rating if there's feedback
    avg_rating = 0
    if total_feedback > 0:
        avg_rating = Feedback.objects.filter(event__in=events).aggregate(avg=models.Avg('rating'))['avg'] or 0

    # Get registration data for chart (last 30 days)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    registrations_by_day = Registration.objects.filter(
        event__in=events,
        registered_at__gte=thirty_days_ago
    ).extra(
        select={'day': "DATE(registered_at)"}
    ).values('day').annotate(count=models.Count('registration_id')).order_by('day')

    # Prepare data for registration trend chart
    registration_dates = []
    registration_counts = []

    for item in registrations_by_day:
        # The 'day' is already a string in format 'YYYY-MM-DD'
        registration_dates.append(item['day'])
        registration_counts.append(item['count'])

    # Get event categories data for pie chart
    categories = EventCategory.objects.filter(event__in=events).distinct()
    category_counts = {}

    for category in categories:
        count = events.filter(category=category).count()
        category_counts[category.name] = count

    category_labels = list(category_counts.keys())
    category_data = list(category_counts.values())

    # Get attendee types data for pie chart
    attendee_types = AttendeeType.objects.filter(registration__event__in=events).distinct()
    attendee_type_counts = {}

    for attendee_type in attendee_types:
        count = Registration.objects.filter(event__in=events, attendee_type=attendee_type).count()
        attendee_type_counts[attendee_type.name] = count

    attendee_type_labels = list(attendee_type_counts.keys())
    attendee_type_data = list(attendee_type_counts.values())

    # Get top events by attendance
    top_events = events.annotate(
        attendees_count=models.Count('registration', filter=models.Q(registration__role__name='attendee'))
    ).order_by('-attendees_count')[:5]

    # Get top events by rating
    top_rated_events = events.annotate(
        avg_rating=models.Avg('feedback__rating')
    ).exclude(avg_rating__isnull=True).order_by('-avg_rating')[:5]

    # Convert data to JSON for JavaScript charts
    import json
    registration_dates_json = json.dumps(registration_dates)
    registration_counts_json = json.dumps(registration_counts)
    category_labels_json = json.dumps(category_labels)
    category_data_json = json.dumps(category_data)
    attendee_type_labels_json = json.dumps(attendee_type_labels)
    attendee_type_data_json = json.dumps(attendee_type_data)

    context = {
        'events': events,
        'total_events': total_events,
        'total_attendees': total_attendees,
        'total_speakers': total_speakers,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
        'top_events': top_events,
        'top_rated_events': top_rated_events,
        'registration_dates': registration_dates_json,
        'registration_counts': registration_counts_json,
        'category_labels': category_labels_json,
        'category_data': category_data_json,
        'attendee_type_labels': attendee_type_labels_json,
        'attendee_type_data': attendee_type_data_json,
    }

    return render(request, 'reports.html', context)

@login_required
def all_registrations(request):
    """
    View function for displaying all registrations across events.
    """
    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Get all registrations for these events
    registrations = Registration.objects.filter(event__in=events).select_related(
        'user', 'event', 'role', 'attendee_type'
    ).order_by('-registered_at')

    # Get event filter parameter
    event_filter = request.GET.get('event')
    if event_filter:
        registrations = registrations.filter(event__event_id=event_filter)

    # Get role filter parameter
    role_filter = request.GET.get('role')
    if role_filter:
        registrations = registrations.filter(role__name=role_filter)

    # Get attendee type filter parameter
    type_filter = request.GET.get('type')
    if type_filter:
        registrations = registrations.filter(attendee_type__name=type_filter)

    # Get all roles and attendee types for filter dropdowns
    roles = ParticipantRole.objects.all()
    attendee_types = AttendeeType.objects.all()

    # Get statistics
    total_registrations = registrations.count()
    attendee_count = registrations.filter(role__name='attendee').count()
    speaker_count = registrations.filter(role__name='speaker').count()

    # Get registration counts by event
    event_registration_counts = {}
    for event in events:
        event_registration_counts[event.event_id] = registrations.filter(event=event).count()

    context = {
        'registrations': registrations,
        'events': events,
        'roles': roles,
        'attendee_types': attendee_types,
        'total_registrations': total_registrations,
        'attendee_count': attendee_count,
        'speaker_count': speaker_count,
        'event_registration_counts': event_registration_counts,
        'event_filter': event_filter,
        'role_filter': role_filter,
        'type_filter': type_filter,
    }

    return render(request, 'all_registrations.html', context)

@login_required
def all_feedback(request):
    """
    View function for displaying all feedback across events.
    """
    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Get all feedback for these events
    feedback_list = Feedback.objects.filter(event__in=events).select_related(
        'user', 'event'
    ).order_by('-feedback_id')

    # Get event filter parameter
    event_filter = request.GET.get('event')
    if event_filter:
        feedback_list = feedback_list.filter(event__event_id=event_filter)

    # Get rating filter parameter
    rating_filter = request.GET.get('rating')
    if rating_filter and rating_filter.isdigit():
        feedback_list = feedback_list.filter(rating=int(rating_filter))

    # Calculate statistics
    total_feedback = feedback_list.count()
    avg_rating = feedback_list.aggregate(avg=models.Avg('rating'))['avg'] or 0

    # Get rating distribution
    rating_distribution = {}
    rating_counts = {}
    for i in range(1, 6):
        count = feedback_list.filter(rating=i).count()
        rating_counts[i] = count
        if total_feedback > 0:
            rating_distribution[i] = int((count / total_feedback) * 100)
        else:
            rating_distribution[i] = 0

    # Get feedback counts by event
    event_feedback_counts = {}
    for event in events:
        event_feedback_counts[event.event_id] = feedback_list.filter(event=event).count()

    # Get top rated events
    top_rated_events = events.annotate(
        avg_rating=models.Avg('feedback__rating'),
        feedback_count=models.Count('feedback')
    ).filter(feedback_count__gt=0).order_by('-avg_rating')[:5]

    context = {
        'feedback_list': feedback_list,
        'events': events,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
        'rating_distribution': rating_distribution,
        'rating_counts': rating_counts,
        'event_feedback_counts': event_feedback_counts,
        'top_rated_events': top_rated_events,
        'event_filter': event_filter,
        'rating_filter': rating_filter,
    }

    return render(request, 'all_feedback.html', context)

@login_required
def event_detail(request, event_id):
    try:
        event = get_object_or_404(Event, event_id=event_id)

        # Get registrations for this event
        registrations = Registration.objects.filter(event=event).select_related('user', 'role', 'attendee_type')

        # Get attendees count
        attendees_count = registrations.filter(role__name='attendee').count()

        # Get speakers count and list
        speakers_count = registrations.filter(role__name='speaker').count()
        speakers = registrations.filter(role__name='speaker').select_related('user')

        # Get event speakers with detailed information
        event_speakers = EventSpeaker.objects.filter(event=event).select_related('speaker', 'speaker__user').order_by('-is_keynote', 'presentation_time')

        # Check if the current user is registered for this event
        user_registration = registrations.filter(user=request.user).first()

        # Get feedback for this event
        feedback = Feedback.objects.filter(event=event).select_related('user')

        # Check if the current user has already submitted feedback
        user_feedback = None
        if request.user.is_authenticated:
            user_feedback = Feedback.objects.filter(event=event, user=request.user).first()

        # Check if the current user is the organizer
        is_organizer = event.organizer == request.user

        # Check if the current user is an attendee
        is_attendee = False
        if user_registration and user_registration.role.name == 'attendee':
            is_attendee = True

        # Determine which base template to use
        if is_organizer:
            base_template = 'organizer/base.html'
        elif is_attendee:
            base_template = 'attendee/base.html'
        else:
            base_template = 'base.html'

        context = {
            'event': event,
            'registrations': registrations,
            'attendees_count': attendees_count,
            'speakers_count': speakers_count,
            'speakers': speakers,
            'event_speakers': event_speakers,
            'user_registration': user_registration,
            'feedback': feedback,
            'user_feedback': user_feedback,
            'is_organizer': is_organizer,
            'is_attendee': is_attendee,
            'base_template': base_template,
            'now': timezone.now(),  # Add current time for registration status checks
        }

        # Use a single template for both organizers and attendees
        return render(request, 'event_detail.html', context)
    except Event.DoesNotExist:
        messages.error(request, 'Event not found')
        return redirect('dashboard')

@login_required
def edit_event(request, event_id):
    """
    View function for editing an existing event.
    """
    event = get_object_or_404(Event, event_id=event_id)

    # Check if the user is the organizer of this event
    if event.organizer != request.user:
        messages.error(request, "You don't have permission to edit this event.")
        return redirect('event_detail', event_id=event_id)

    # Get current attendee count for context
    attendee_count = Registration.objects.filter(event=event, role__name='attendee').count()
    available_seats = max(0, event.capacity - attendee_count)

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            # Handle custom registration link
            custom_link = form.cleaned_data.get('custom_registration_link')
            if not custom_link:
                # If the user unchecked the custom link option, clear the link to regenerate
                if event.registration_link and not event.registration_link.startswith('/events/register/'):
                    form.instance.registration_link = ''

            # Save the form but get the updated event
            updated_event = form.save()

            # Handle speaker assignments
            speakers = form.cleaned_data.get('speakers')
            keynote_speaker = form.cleaned_data.get('keynote_speaker')
            speaker_topics_text = form.cleaned_data.get('speaker_topics', '')
            notify_speakers = form.cleaned_data.get('notify_speakers', True)

            # Parse speaker topics
            speaker_topics = {}
            if speaker_topics_text:
                lines = speaker_topics_text.strip().split('\n')
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        name = parts[0].strip()
                        topic = parts[1].strip()
                        speaker_topics[name] = topic

            # Get existing event speakers
            existing_speakers = set(EventSpeaker.objects.filter(event=event).values_list('speaker__user__user_id', flat=True))

            # Get new speakers list
            new_speakers = set()
            if speakers:
                new_speakers = set(speaker.user_id for speaker in speakers)

            # Speakers to remove
            speakers_to_remove = existing_speakers - new_speakers

            # Speakers to add
            speakers_to_add = new_speakers - existing_speakers

            # Remove speakers that are no longer assigned
            if speakers_to_remove:
                EventSpeaker.objects.filter(
                    event=event,
                    speaker__user__user_id__in=speakers_to_remove
                ).delete()

            # Process each speaker to add or update
            if speakers:
                speaker_role = ParticipantRole.objects.get(name='speaker')

                for user in speakers:
                    # Skip if this speaker is not new and not the keynote (we'll update keynote status separately)
                    if user.user_id not in speakers_to_add and (not keynote_speaker or user != keynote_speaker):
                        continue

                    # Get or create Speaker object
                    speaker, created = Speaker.objects.get_or_create(
                        user=user,
                        defaults={'bio': f"Bio for {user.get_full_name() or user.email}"}
                    )

                    # Determine if this is the keynote speaker
                    is_keynote = (keynote_speaker and user == keynote_speaker)

                    # Find topic for this speaker
                    topic = ""
                    speaker_name = user.get_full_name()
                    if speaker_name in speaker_topics:
                        topic = speaker_topics[speaker_name]

                    # If this is a new speaker, create the EventSpeaker relationship
                    if user.user_id in speakers_to_add:
                        event_speaker = EventSpeaker.objects.create(
                            event=event,
                            speaker=speaker,
                            topic=topic,
                            is_keynote=is_keynote,
                            presentation_time=event.start_date  # Default to event start time
                        )

                        # Create registration for the speaker if it doesn't exist
                        if not Registration.objects.filter(event=event, user=user).exists():
                            Registration.objects.create(
                                event=event,
                                user=user,
                                role=speaker_role
                            )

                        # Send notification to the speaker
                        if notify_speakers:
                            # Create in-app notification
                            create_notification(
                                user=user,
                                event=event,
                                notification_type='speaker_added',
                                title='Speaker Assignment',
                                message=f"You have been assigned as a speaker for '{event.title}'." +
                                        (f" Topic: {topic}" if topic else ""),
                                icon='fa-microphone',
                                color='success',
                                action_url=f"/events/events/{event.event_id}/"
                            )

                            # Send email notification
                            send_speaker_assignment_email(user, event, topic, is_keynote)
                    else:
                        # Update existing EventSpeaker
                        event_speaker = EventSpeaker.objects.get(event=event, speaker=speaker)
                        event_speaker.is_keynote = is_keynote
                        if topic:
                            event_speaker.topic = topic
                        event_speaker.save()

            # Create notifications for all registered users
            registrations = Registration.objects.filter(event=event).exclude(user=request.user)

            for registration in registrations:
                # Only notify users who have enabled updates
                if registration.updates_enabled:
                    create_notification(
                        user=registration.user,
                        event=updated_event,
                        notification_type='event_updated',
                        title='Event Updated',
                        message=f"The event '{updated_event.title}' has been updated.",
                        icon='fa-edit',
                        color='success',
                        action_url=f"/events/events/{updated_event.event_id}/"
                    )

            messages.success(request, f"Event '{event.title}' updated successfully!")
            return redirect('event_detail', event_id=event.event_id)
    else:
        # Set initial value for custom_registration_link based on current link
        initial_data = {'custom_registration_link': event.registration_link and not event.registration_link.startswith('/events/register/')}
        form = EventForm(instance=event, initial=initial_data)

    context = {
        'form': form,
        'event': event,
        'edit_mode': True,
        'attendee_count': attendee_count,
        'available_seats': available_seats,
    }

    return render(request, 'organizer/edit_event.html', context)

def logout_view(request):
    """
    View function to log the user out and redirect to the home page.
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('index')

def event_admin(request):
    """
    View function for the admin login page.
    Also handles the login form submission directly.
    """
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    # Handle form submission directly in this view
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, username=email, password=password)

            if user is not None and user.is_staff:
                login(request, user)
                # Redirect to our custom admin dashboard
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid admin credentials or insufficient permissions.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')

    # Render the login form
    return render(request, 'event_admin.html', {})

def event_admin_submit(request):
    """
    View function to handle the admin login form submission.
    """
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, username=email, password=password)

            if user is not None and user.is_staff:
                login(request, user)
                # Redirect to our custom admin dashboard instead of Django admin
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid admin credentials or insufficient permissions.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')

    return redirect('event_admin')


@login_required
@user_passes_test(lambda u: u.is_staff)
def create_admin_user(request):
    """
    View function for creating a new admin user.
    Only accessible to staff users.
    """
    from .forms import AdminUserCreationForm

    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Admin user '{user.email}' created successfully!")
            return redirect('admin_dashboard')
    else:
        form = AdminUserCreationForm()

    context = {
        'form': form,
        'section': 'users'
    }

    return render(request, 'admin_dashboard/create_admin.html', context)


def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    # Use short variable names
    sUrl = settings.STATIC_URL      # Typically /static/
    sRoot = settings.STATIC_ROOT    # Typically /home/user/project_static/
    mUrl = settings.MEDIA_URL       # Typically /media/
    mRoot = settings.MEDIA_ROOT     # Typically /home/user/project_static/media/

    # Convert URIs to absolute system paths
    if uri.startswith(mUrl):
        path = os.path.join(mRoot, uri.replace(mUrl, ""))
    elif uri.startswith(sUrl):
        path = os.path.join(sRoot, uri.replace(sUrl, ""))
    elif uri.startswith('/'):
        # Handle relative paths that start with a slash
        path = uri.replace('/', '')
        if os.path.isfile(os.path.join(mRoot, path)):
            path = os.path.join(mRoot, path)
        elif os.path.isfile(os.path.join(sRoot, path)):
            path = os.path.join(sRoot, path)
        else:
            return uri
    else:
        return uri  # Handle absolute uri (i.e. http://some.tld/foo.png)

    # Make sure that file exists
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return uri

    return path


@login_required
def feedback_pdf(request):
    """
    Generate a PDF of the feedback data
    """
    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Get all feedback for these events
    feedback_list = Feedback.objects.filter(event__in=events).select_related(
        'user', 'event'
    ).order_by('-feedback_id')

    # Get event filter parameter
    event_filter = request.GET.get('event')
    event_name = None
    if event_filter:
        feedback_list = feedback_list.filter(event__event_id=event_filter)
        event = Event.objects.filter(event_id=event_filter).first()
        if event:
            event_name = event.title

    # Get rating filter parameter
    rating_filter = request.GET.get('rating')
    if rating_filter and rating_filter.isdigit():
        feedback_list = feedback_list.filter(rating=int(rating_filter))

    # Calculate statistics
    total_feedback = feedback_list.count()
    avg_rating = feedback_list.aggregate(avg=models.Avg('rating'))['avg'] or 0
    events_count = events.count()

    # Get rating distribution
    rating_distribution = {}
    rating_counts = {}
    for i in range(1, 6):
        count = feedback_list.filter(rating=i).count()
        rating_counts[i] = count
        if total_feedback > 0:
            rating_distribution[i] = int((count / total_feedback) * 100)
        else:
            rating_distribution[i] = 0

    # Get top rated events
    top_rated_events = events.annotate(
        avg_rating=models.Avg('feedback__rating'),
        feedback_count=models.Count('feedback')
    ).filter(feedback_count__gt=0).order_by('-avg_rating')[:5]

    # Create a template filter to get dictionary items by key
    from django.template.defaulttags import register
    @register.filter
    def get_item(dictionary, key):
        return dictionary.get(str(key))

    # Prepare context for the PDF template
    context = {
        'feedback_list': feedback_list,
        'events_count': events_count,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
        'rating_distribution': rating_distribution,
        'rating_counts': rating_counts,
        'top_rated_events': top_rated_events,
        'event_filter': event_filter,
        'event_name': event_name,
        'rating_filter': rating_filter,
        'now': timezone.now(),
    }

    # Render the template
    template = get_template('feedback_pdf.html')
    html = template.render(context)

    # Create the PDF response
    response = HttpResponse(content_type='application/pdf')
    filename = "feedback_report"
    if event_name:
        filename += f"_{event_name}"
    if rating_filter:
        filename += f"_rating_{rating_filter}"
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'

    # Generate PDF
    pisa_status = pisa.CreatePDF(
        html, dest=response, link_callback=link_callback)

    # Return the response
    if pisa_status.err:
        return HttpResponse('We had some errors with code %s <pre>%s</pre>' % (pisa_status.err, html))
    return response


@login_required
def event_pdf(request, event_id):
    """Generate PDF ticket for an event"""
    event = get_object_or_404(Event, event_id=event_id)
    registration = get_object_or_404(Registration, event=event, user=request.user)
    
    # Generate QR code
    qr_code = generate_ticket_qr(event, registration)
    
    # Render ticket template
    template = get_template('ticket_template.html')
    context = {
        'event': event,
        'registration': registration,
        'qr_code': qr_code,
    }
    html = template.render(context)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{event.title}_{registration.registration_id}.pdf"'
    
    # Convert HTML to PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF ticket', status=500)
    
    return response

@login_required
def register_event(request, event_id):
    """
    View function to handle event registration for attendees.
    """
    event = get_object_or_404(Event, event_id=event_id)
    
    # Check if registration is enabled for this event
    if not event.enable_registration:
        messages.error(request, "Registration for this event is closed.")
        return redirect('event_detail', event_id=event_id)
    
    # Check if event has already started
    if timezone.now() >= event.start_date:
        messages.error(request, "Registration is closed. The event has already started.")
        return redirect('event_detail', event_id=event_id)
    
    # Check if the event is full
    if event.is_full():
        messages.error(request, "Sorry, this event has reached its maximum capacity.")
        return redirect('event_detail', event_id=event_id)
    
    # Check if user is already registered
    if Registration.objects.filter(event=event, user=request.user).exists():
        messages.warning(request, "You are already registered for this event.")
        return redirect('event_detail', event_id=event_id)
    
    if request.method == 'POST':
        # Update user profile with form data
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', '')
        user.organization = request.POST.get('organization', '')
        user.designation = request.POST.get('designation', '')
        user.save()

        try:
            # Get the attendee type by ID
            attendee_type = AttendeeType.objects.get(type_id=request.POST.get('attendee_type'))
            
            # Create registration
            registration = Registration.objects.create(
                user=user,
                event=event,
                role=ParticipantRole.objects.get(name='attendee'),
                attendee_type=attendee_type,
                dietary_requirements=request.POST.get('dietary_requirements', ''),
                special_assistance=request.POST.get('special_assistance', ''),
                reminders_enabled=request.POST.get('reminders_enabled') == 'on',
                updates_enabled=request.POST.get('updates_enabled') == 'on',
                agreed_to_terms=True
            )
            
            # Send confirmation email
            send_registration_confirmation(request, registration)
            
            messages.success(request, "You have successfully registered for this event!")
            return redirect('event_detail', event_id=event_id)
            
        except AttendeeType.DoesNotExist:
            messages.error(request, "Invalid attendee type selected.")
            return redirect('register_event', event_id=event_id)
        except Exception as e:
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return redirect('register_event', event_id=event_id)
    
    # Get all attendee types for the form
    attendee_types = AttendeeType.objects.all()
    
    context = {
        'event': event,
        'user': request.user,
        'attendee_types': attendee_types,
    }
    return render(request, 'event_registration_form.html', context)

def send_registration_confirmation(request, registration):
    """
    Send a confirmation email to the user after successful registration.
    """
    # Generate QR code with detailed ticket information
    ticket_data = f"Event: {registration.event.title}\n" \
                 f"Attendee: {request.user.first_name} {request.user.last_name}\n" \
                 f"Ticket ID: {registration.registration_id}\n" \
                 f"Category: {registration.event.category.name}\n" \
                 f"Type: {registration.attendee_type.name if registration.attendee_type else 'Standard'}\n" \
                 f"Start: {registration.event.start_date.strftime('%Y-%m-%d %H:%M')}\n" \
                 f"End: {registration.event.end_date.strftime('%Y-%m-%d %H:%M')}\n" \
                 f"Location: {registration.event.location}\n" \
                 f"Organizer: {registration.event.organizer.get_full_name()}"
    
    qr_code_base64 = generate_qr_code_base64(ticket_data)

    subject = f"Registration Confirmed - {registration.event.title}"
    context = {
        'user': request.user,
        'event': registration.event,
        'registration': registration,
        'qr_code': qr_code_base64,
        'base_url': request.build_absolute_uri('/').rstrip('/')
    }
    html_message = render_to_string('emails/registration_confirmation.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        # Log the error but don't stop the registration process
        print(f"Failed to send registration confirmation email: {str(e)}")


@login_required
def update_notification_preferences(request, event_id):
    """
    View function to update notification preferences for an event registration
    """
    if request.method == 'POST':
        try:
            event = get_object_or_404(Event, event_id=event_id)
            registration = get_object_or_404(Registration, event=event, user=request.user)

            # Parse the JSON data from the request body
            data = json.loads(request.body)

            # Update the registration preferences
            registration.reminders_enabled = data.get('reminders_enabled', False)
            registration.updates_enabled = data.get('updates_enabled', False)
            registration.save()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def share_event_email(request, event_id):
    """
    View function to share an event via email
    """
    if request.method == 'POST':
        try:
            event = get_object_or_404(Event, event_id=event_id)

            # Parse the JSON data from the request body
            data = json.loads(request.body)
            recipient_email = data.get('email')
            message = data.get('message', '')

            # In a real application, you would send an email here
            # For now, we'll just return a success response

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def email_attendees(request, event_id):
    """
    View function for sending emails to event attendees
    """
    try:
        # Get event and verify organizer
        event = get_object_or_404(Event, event_id=event_id)
        if request.user != event.organizer:
            logger.warning(f"Unauthorized access attempt by {request.user} for event {event_id}")
            messages.error(request, "You don't have permission to email attendees for this event.")
            return redirect('event_detail', event_id=event_id)

        # Get attendees
        attendees = Registration.objects.filter(
            event=event,
            role__name='attendee'
        ).select_related('user')
        
        logger.info(f"Found {attendees.count()} attendees for event {event_id}")

        if request.method == 'POST':
            try:
                subject = request.POST.get('subject', '').strip()
                message = request.POST.get('message', '').strip()
                include_event_details = request.POST.get('include_event_details') == 'on'

                # Validate input
                if not subject or not message:
                    logger.warning("Missing subject or message")
                    messages.error(request, "Please provide both subject and message.")
                    return render(request, 'events/email_attendees.html', {
                        'event': event,
                        'attendees': attendees
                    })

                # Add event details if requested
                if include_event_details:
                    try:
                        event_details = f"""

Event Details:
-------------
Title: {event.title}
Date & Time: {event.start_date.strftime('%B %d, %Y %I:%M %p')} - {event.end_date.strftime('%I:%M %p')}
Location: {event.location}
Description: {event.description}

Duration: {event.get_duration_in_hours()} hours
Status: {event.get_status()}
"""
                        message += event_details
                    except AttributeError as e:
                        logger.error(f"Event attribute error: {str(e)}")
                        messages.error(request, f"Error accessing event details: {str(e)}")
                        return render(request, 'events/email_attendees.html', {
                            'event': event,
                            'attendees': attendees
                        })

                recipient_list = [attendee.user.email for attendee in attendees]
                
                if not recipient_list:
                    logger.warning(f"No attendees found for event {event_id}")
                    messages.warning(request, "No attendees found to email.")
                    return render(request, 'events/email_attendees.html', {
                        'event': event,
                        'attendees': attendees
                    })

                try:
                    # Test SMTP connection first
                    connection = get_connection()
                    try:
                        connection.open()
                        logger.info("SMTP connection test successful")

                        # Send the email
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=recipient_list,
                            fail_silently=False,
                            connection=connection
                        )
                        
                        logger.info(f"Email sent successfully to {len(recipient_list)} attendees")
                        messages.success(request, f"Email sent successfully to {len(recipient_list)} attendees!")
                        return redirect('event_detail', event_id=event_id)

                    except SMTPAuthenticationError as e:
                        error_detail = f"""
Gmail Authentication Failed!

Error Details:
- Type: {type(e).__name__}
- Message: {str(e)}
- Location: {traceback.extract_tb(e.__traceback__)[-1]}

Please check:
1. 2-Step Verification is enabled at https://myaccount.google.com/security
2. App Password is correct (16 characters, no spaces)
3. Email settings in .env file are correct:
   Current Email: {settings.EMAIL_HOST_USER}
   Password Length: {len(settings.EMAIL_HOST_PASSWORD)} characters
   TLS Enabled: {settings.EMAIL_USE_TLS}
   Port: {settings.EMAIL_PORT}
"""
                        logger.error(f"SMTP Authentication Error: {str(e)}")
                        messages.error(request, error_detail)
                    finally:
                        connection.close()

                except SMTPException as e:
                    error_detail = f"""
SMTP Error while sending email:
- Error Type: {type(e).__name__}
- Message: {str(e)}
- Location: {traceback.extract_tb(e.__traceback__)[-1]}
- Recipients: {', '.join(recipient_list)}
"""
                    logger.error(f"SMTP Error: {str(e)}")
                    messages.error(request, error_detail)

                except Exception as e:
                    error_detail = f"""
Unexpected error while sending email:
- Error Type: {type(e).__name__}
- Error Message: {str(e)}
- Location: {traceback.extract_tb(e.__traceback__)[-1]}
- View: email_attendees
- Event ID: {event_id}
"""
                    logger.error(f"Unexpected error sending email: {str(e)}\n{traceback.format_exc()}")
                    messages.error(request, error_detail)

            except Exception as e:
                error_detail = f"""
Error processing email request:
- Error Type: {type(e).__name__}
- Error Message: {str(e)}
- Location: {traceback.extract_tb(e.__traceback__)[-1]}
- View: email_attendees
- Event ID: {event_id}
"""
                logger.error(f"Error processing email request: {str(e)}\n{traceback.format_exc()}")
                messages.error(request, error_detail)

            return render(request, 'events/email_attendees.html', {
                'event': event,
                'attendees': attendees
            })

        # GET request - display form
        return render(request, 'events/email_attendees.html', {
            'event': event,
            'attendees': attendees
        })

    except Exception as e:
        error_detail = f"""
Unexpected error in view:
- Error Type: {type(e).__name__}
- Error Message: {str(e)}
- Location: {traceback.extract_tb(e.__traceback__)[-1]}
- View: email_attendees
- Event ID: {event_id}

Full Traceback:
{traceback.format_exc()}
"""
        logger.error(f"Error in email_attendees view: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, error_detail)
        return redirect('event_detail', event_id=event_id)


@login_required
def export_registrations_csv(request, event_id):
    """
    View function to export event registrations as CSV
    """
    try:
        # Get the event
        event = get_object_or_404(Event, event_id=event_id)

        # Check if the user is the organizer
        if request.user != event.organizer:
            messages.error(request, "You don't have permission to export registrations for this event.")
            return redirect('event_detail', event_id=event_id)

        # Get all registrations for this event
        registrations = Registration.objects.filter(event=event).select_related(
            'user', 'role', 'attendee_type'
        ).order_by('-registered_at')

        # Create the HttpResponse with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{event.title}_registrations.csv"'

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row
        writer.writerow([
            'Name',
            'Email',
            'Role',
            'Attendee Type',
            'Registration Date',
            'Phone Number',
            'Company/Organization'
        ])

        # Write data rows
        for registration in registrations:
            writer.writerow([
                f"{registration.user.first_name} {registration.user.last_name}",
                registration.user.email,
                registration.role.name.title(),
                registration.attendee_type.name.title() if registration.attendee_type else "N/A",
                registration.registered_at.strftime('%Y-%m-%d %H:%M'),
                registration.user.phone or "N/A",
                registration.user.company or "N/A"
            ])

        return response

    except Exception as e:
        messages.error(request, f"Error exporting registrations: {str(e)}")
        return redirect('event_detail', event_id=event_id)


@login_required
def submit_feedback(request, event_id):
    """
    View function to submit feedback for an event
    """
    if request.method == 'POST':
        try:
            # Set up logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Feedback submission started for event {event_id} by user {request.user.email}")
            
            event = get_object_or_404(Event, event_id=event_id)
            logger.info(f"Event found: {event.title}")
            
            # Check if the user is registered for this event
            registration = Registration.objects.filter(
                event=event,
                user=request.user,
                role__name='attendee'
            ).first()

            if not registration:
                logger.warning(f"User {request.user.email} not registered as attendee for event {event_id}")
                messages.error(request, "You must be registered as an attendee for this event to submit feedback.")
                return JsonResponse({'status': 'error', 'message': "You must be registered as an attendee for this event to submit feedback."})

            # Check if the user has already submitted feedback for this event
            existing_feedback = Feedback.objects.filter(event=event, user=request.user).exists()
            if existing_feedback:
                logger.warning(f"User {request.user.email} already submitted feedback for event {event_id}")
                messages.warning(request, "You have already submitted feedback for this event.")
                return JsonResponse({'status': 'error', 'message': "You have already submitted feedback for this event."})

            # Get the rating and comments from the form
            rating = request.POST.get('rating')
            comments = request.POST.get('comments', '').strip()
            
            logger.info(f"Received feedback - Rating: {rating}, Comments length: {len(comments) if comments else 0}")

            # Validate the input
            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
                logger.warning(f"Invalid rating value: {rating}")
                messages.error(request, "Please provide a valid rating between 1 and 5.")
                return JsonResponse({'status': 'error', 'message': "Please provide a valid rating between 1 and 5."})

            if not comments:
                logger.warning("Empty comments submitted")
                messages.error(request, "Please provide some comments with your feedback.")
                return JsonResponse({'status': 'error', 'message': "Please provide some comments with your feedback."})

            try:
                # Create the feedback
                feedback = Feedback.objects.create(
                    event=event,
                    user=request.user,
                    rating=int(rating),
                    comments=comments
                )
                logger.info(f"Feedback successfully created with ID: {feedback.feedback_id}")

                messages.success(request, "Thank you for your feedback! Your input helps us improve future events.")
                return JsonResponse({'status': 'success', 'message': "Thank you for your feedback! Your input helps us improve future events."})
            except Exception as e:
                logger.error(f"Error creating feedback: {str(e)}", exc_info=True)
                messages.error(request, "There was an error saving your feedback. Please try again.")
                return JsonResponse({'status': 'error', 'message': "There was an error saving your feedback. Please try again."})

        except Event.DoesNotExist:
            logger.error(f"Event not found: {event_id}")
            messages.error(request, "Event not found.")
            return JsonResponse({'status': 'error', 'message': "Event not found."})
        except Exception as e:
            logger.error(f"Unexpected error in submit_feedback view: {str(e)}", exc_info=True)
            messages.error(request, "There was an error submitting your feedback. Please try again.")
            return JsonResponse({'status': 'error', 'message': "There was an error submitting your feedback. Please try again."})

    return redirect('event_detail', event_id=event_id)


@login_required
def my_reviews(request):
    """
    View function for the attendee's reviews page.
    """
    # Get all reviews submitted by the current user
    reviews = Feedback.objects.filter(user=request.user).select_related('event', 'event__category').order_by('-feedback_id')

    # Calculate statistics
    total_reviews = reviews.count()
    avg_rating = reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0
    reviewed_events_count = reviews.values('event').distinct().count()

    # Get all events the user is registered for
    registrations = Registration.objects.filter(user=request.user).select_related('event')
    registered_events = [reg.event for reg in registrations]

    # Get events that need reviews (past events without feedback)
    now = timezone.now()
    past_events = [event for event in registered_events if event.end_date < now]
    reviewed_event_ids = reviews.values_list('event__event_id', flat=True)
    pending_reviews = [event for event in past_events if event.event_id not in reviewed_event_ids]
    pending_reviews_count = len(pending_reviews)

    # Get rating distribution
    rating_distribution = {}
    rating_counts = {}
    for i in range(1, 6):
        count = reviews.filter(rating=i).count()
        rating_counts[i] = count
        if total_reviews > 0:
            rating_distribution[i] = int((count / total_reviews) * 100)
        else:
            rating_distribution[i] = 0

    # Create a template filter to get dictionary items by key
    from django.template.defaulttags import register
    @register.filter
    def get_item(dictionary, key):
        return dictionary.get(str(key))

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(reviews, 10)  # Show 10 reviews per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'reviews': page_obj,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'reviewed_events_count': reviewed_events_count,
        'pending_reviews': pending_reviews[:6],  # Limit to 6 for display
        'pending_reviews_count': pending_reviews_count,
        'rating_distribution': rating_distribution,
        'rating_counts': rating_counts,
        'user_role': 'Attendee'
    }

    return render(request, 'attendee/my_reviews.html', context)


# --- Notification System Functions ---

@login_required
def get_notifications(request):
    """
    View function to get notifications for the current user.
    """
    # Get unread notifications for the current user
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]

    # Format notifications for JSON response
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': str(notification.id),
            'title': notification.title,
            'message': notification.message,
            'icon_class': notification.icon_class,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%b %d, %Y %H:%M'),
            'time_since': notification.time_since,
            'related_event': str(notification.related_event.event_id) if notification.related_event else None
        })

    # Count unread notifications
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': unread_count
    })

@login_required
def mark_notification_read(request, id):
    """
    View function to mark a notification as read.
    """
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=id, user=request.user)
            notification.mark_as_read()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required
def mark_all_notifications_read(request):
    """
    View function to mark all notifications as read.
    """
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required
def notification_preferences(request):
    """
    View function to update notification preferences.
    """
    if request.method == 'POST':
        # Get the user's registrations
        registrations = Registration.objects.filter(user=request.user)

        # Update email notification preferences
        email_notifications = request.POST.get('email_notifications') == 'on'
        for registration in registrations:
            registration.updates_enabled = email_notifications
            registration.save()

        messages.success(request, 'Notification preferences updated successfully!')
        return redirect('attendee_dashboard')

    # Get current preferences
    has_email_enabled = Registration.objects.filter(user=request.user, updates_enabled=True).exists()

    context = {
        'email_notifications': has_email_enabled,
        'user_role': 'Attendee'
    }

    return render(request, 'attendee/notification_preferences.html', context)

# Helper function to create notifications
def create_notification(user, event, notification_type, title, message, icon='fa-bell', color='primary', action_url=''):
    """
    Helper function to create a notification.
    """
    notification = Notification.objects.create(
        user=user,
        event=event,
        notification_type=notification_type,
        title=title,
        message=message,
        icon=icon,
        color=color,
        action_url=action_url
    )

    # Send email notification if user has enabled email updates
    if Registration.objects.filter(user=user, event=event, updates_enabled=True).exists():
        send_notification_email(user, title, message, event)

    return notification

# Helper function to send notification emails
def send_notification_email(user, title, message, event):
    """
    Helper function to send an email notification.
    """
    subject = f'Event Manager: {title}'
    context = {
        'user': user,
        'title': title,
        'message': message,
        'event': event,
        'event_url': f'/events/events/{event.event_id}/'
    }

    # Render email templates
    html_message = render_to_string('emails/notification_email.html', context)
    plain_message = strip_tags(html_message)

    # Send email
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Helper function to send speaker assignment emails
def send_speaker_assignment_email(user, event, topic, is_keynote):
    """
    Helper function to send an email notification to a speaker about their assignment.
    """
    role_text = "keynote speaker" if is_keynote else "speaker"
    subject = f'Speaker Assignment: {event.title}'

    context = {
        'user': user,
        'event': event,
        'topic': topic,
        'is_keynote': is_keynote,
        'role_text': role_text,
        'event_url': f'/events/events/{event.event_id}/',
        'speaker_dashboard_url': '/events/dashboard/speaker/'
    }

    # Render email templates
    html_message = render_to_string('emails/speaker_assignment_email.html', context)
    plain_message = strip_tags(html_message)

    # Send email
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Function to create event reminders
@login_required
@user_passes_test(lambda u: u.is_staff)
def create_event_reminders(request):
    """
    View function to create reminders for upcoming events.
    This would typically be called by a scheduled task/cron job,
    but can also be triggered manually by an admin user.
    """
    # Get events starting in the next 24 hours
    now = timezone.now()
    tomorrow = now + timezone.timedelta(hours=24)
    upcoming_events = Event.objects.filter(start_date__gte=now, start_date__lte=tomorrow)

    notifications_created = 0

    for event in upcoming_events:
        # Get all registrations for this event
        registrations = Registration.objects.filter(event=event, reminders_enabled=True)

        for registration in registrations:
            # Create a notification for each registered user
            create_notification(
                user=registration.user,
                event=event,
                notification_type='event_reminder',
                title='Event Reminder',
                message=f"Your event '{event.title}' is starting soon on {event.start_date.strftime('%B %d at %I:%M %p')}.",
                icon='fa-clock',
                color='warning',
                action_url=f"/events/events/{event.event_id}/"
            )
            notifications_created += 1

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'events_count': len(upcoming_events),
            'notifications_count': notifications_created
        })
    else:
        messages.success(request, f"Created {notifications_created} reminders for {len(upcoming_events)} upcoming events.")
        return redirect('admin:index')

@login_required
def download_report(request, report_type):
    """
    View function to generate and download different types of reports.
    """
    # Get all events created by the current user
    events = Event.objects.filter(organizer=request.user).order_by('-start_date')

    # Get the date range filter if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date and end_date:
        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d')
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d')
            events = events.filter(start_date__gte=start_date, end_date__lte=end_date)
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
            return redirect('reports')

    # Common statistics
    total_events = events.count()
    total_attendees = Registration.objects.filter(event__in=events, role__name='attendee').count()
    total_speakers = Registration.objects.filter(event__in=events, role__name='speaker').count()
    total_feedback = Feedback.objects.filter(event__in=events).count()
    avg_rating = Feedback.objects.filter(event__in=events).aggregate(avg=models.Avg('rating'))['avg'] or 0

    if report_type == 'analytics':
        # Analytics Report
        context = {
            'report_type': 'Analytics Report',
            'events': events,
            'total_events': total_events,
            'total_attendees': total_attendees,
            'total_speakers': total_speakers,
            'total_feedback': total_feedback,
            'avg_rating': avg_rating,
            'registration_data': get_registration_data(events),
            'category_data': get_category_data(events),
            'attendee_type_data': get_attendee_type_data(events),
            'top_events': get_top_events(events),
            'now': timezone.now(),
        }
        template_name = 'reports/analytics_report.html'
        filename = 'analytics_report.pdf'

    elif report_type == 'registration':
        # Registration Report
        context = {
            'report_type': 'Registration Report',
            'events': events,
            'total_registrations': total_attendees,
            'registration_data': get_detailed_registration_data(events),
            'registration_trends': get_registration_trends(events),
            'now': timezone.now(),
        }
        template_name = 'reports/registration_report.html'
        filename = 'registration_report.pdf'

    elif report_type == 'feedback':
        # Feedback Report
        context = {
            'report_type': 'Feedback Report',
            'events': events,
            'total_feedback': total_feedback,
            'avg_rating': avg_rating,
            'feedback_data': get_detailed_feedback_data(events),
            'rating_distribution': get_rating_distribution(events),
            'now': timezone.now(),
        }
        template_name = 'reports/feedback_report.html'
        filename = 'feedback_report.pdf'

    elif report_type == 'financial':
        # Financial Report
        context = {
            'report_type': 'Financial Report',
            'events': events,
            'financial_data': get_financial_data(events),
            'revenue_trends': get_revenue_trends(events),
            'now': timezone.now(),
        }
        template_name = 'reports/financial_report.html'
        filename = 'financial_report.pdf'

    else:
        messages.error(request, "Invalid report type.")
        return redirect('reports')

    # Render the template
    template = get_template(template_name)
    html = template.render(context)

    # Create the PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('We had some errors generating the PDF: <pre>' + html + '</pre>')
    return response

# Helper functions for report data
def get_registration_data(events):
    """Get registration statistics for events"""
    return Registration.objects.filter(event__in=events).values('event__title').annotate(
        total=models.Count('registration_id'),
        attendees=models.Count('registration_id', filter=models.Q(role__name='attendee')),
        speakers=models.Count('registration_id', filter=models.Q(role__name='speaker'))
    )

def get_category_data(events):
    """Get event distribution by category"""
    return events.values('category__name').annotate(
        count=models.Count('event_id')
    ).order_by('-count')

def get_attendee_type_data(events):
    """Get attendee distribution by type"""
    return Registration.objects.filter(event__in=events).values('attendee_type__name').annotate(
        count=models.Count('registration_id')
    ).order_by('-count')

def get_top_events(events):
    """Get top events by attendance"""
    return events.annotate(
        attendees_count=models.Count('registration', filter=models.Q(registration__role__name='attendee'))
    ).order_by('-attendees_count')[:5]

def get_detailed_registration_data(events):
    """Get detailed registration data for each event"""
    return Registration.objects.filter(event__in=events).select_related(
        'user', 'event', 'role', 'attendee_type'
    ).order_by('-registered_at')

def get_registration_trends(events):
    """Get registration trends over time"""
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    return Registration.objects.filter(
        event__in=events,
        registered_at__gte=thirty_days_ago
    ).extra(
        select={'day': "DATE(registered_at)"}
    ).values('day').annotate(
        count=models.Count('registration_id')
    ).order_by('day')

def get_detailed_feedback_data(events):
    """Get detailed feedback data for each event"""
    return Feedback.objects.filter(event__in=events).select_related(
        'user', 'event'
    ).order_by('-feedback_id')

def get_rating_distribution(events):
    """Get rating distribution for events"""
    return Feedback.objects.filter(event__in=events).values('rating').annotate(
        count=models.Count('feedback_id')
    ).order_by('rating')

def get_financial_data(events):
    """Get financial data for events"""
    return events.annotate(
        total_revenue=models.Sum('sponsor__sponsorship_amount'),
        total_sponsors=models.Count('sponsor', distinct=True),
        avg_sponsorship=models.Avg('sponsor__sponsorship_amount')
    )

def get_revenue_trends(events):
    """Get revenue trends over time"""
    return events.values('start_date__month').annotate(
        revenue=models.Sum('sponsor__sponsorship_amount')
    ).order_by('start_date__month')

@login_required
def my_tickets(request):
    """
    View function for displaying all tickets/registrations for an attendee.
    """
    # Get all registrations for the current user where they are an attendee
    registrations = Registration.objects.filter(
        user=request.user,
        role__name='attendee'
    ).select_related('event', 'attendee_type').order_by('-event__start_date')

    # Separate registrations into upcoming and past events
    now = timezone.now()
    upcoming_registrations = []
    past_registrations = []

    for reg in registrations:
        if reg.event.end_date >= now:
            upcoming_registrations.append(reg)
        else:
            past_registrations.append(reg)

    # Get statistics
    total_tickets = registrations.count()
    upcoming_count = len(upcoming_registrations)
    past_count = len(past_registrations)
    
    # Get event categories attended
    categories_attended = set(reg.event.category.name for reg in registrations)
    
    context = {
        'upcoming_registrations': upcoming_registrations,
        'past_registrations': past_registrations,
        'total_tickets': total_tickets,
        'upcoming_count': upcoming_count,
        'past_count': past_count,
        'categories_attended': categories_attended,
        'user_role': 'Attendee'
    }
    
    return render(request, 'attendee/my_tickets.html', context)

@login_required
def attendee_profile(request):
    """
    View function for the attendee's profile page.
    """
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        organization = request.POST.get('organization')
        designation = request.POST.get('designation')
        email_notifications = request.POST.get('email_notifications') == 'on'
        
        # Update user profile
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone = phone
        user.organization = organization
        user.designation = designation
        
        # Handle password change if provided
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if current_password and new_password and confirm_password:
            if user.check_password(current_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    messages.success(request, 'Password updated successfully.')
                else:
                    messages.error(request, 'New passwords do not match.')
                    return redirect('attendee_profile')
            else:
                messages.error(request, 'Current password is incorrect.')
                return redirect('attendee_profile')
        
        user.save()
        
        # Update notification preferences for all registrations
        Registration.objects.filter(user=user).update(updates_enabled=email_notifications)
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('attendee_profile')
    
    # Get user's activity statistics
    total_events = Registration.objects.filter(user=request.user, role__name='attendee').count()
    total_reviews = Feedback.objects.filter(user=request.user).count()
    categories_count = Event.objects.filter(
        registration__user=request.user,
        registration__role__name='attendee'
    ).values('category').distinct().count()
    
    # Get email notification preference
    email_notifications = Registration.objects.filter(
        user=request.user,
        updates_enabled=True
    ).exists()
    
    context = {
        'user': request.user,
        'total_events': total_events,
        'total_reviews': total_reviews,
        'categories_count': categories_count,
        'email_notifications': email_notifications,
        'user_role': 'Attendee'
    }
    
    return render(request, 'attendee/profile.html', context)

@login_required
def export_all_registrations(request):
    """
    View function to export all registrations as CSV with filters
    """
    try:
        # Get all events created by the current user
        events = Event.objects.filter(organizer=request.user)

        # Get all registrations for these events
        registrations = Registration.objects.filter(event__in=events).select_related(
            'user', 'event', 'role', 'attendee_type'
        )

        # Apply filters if provided
        event_filter = request.GET.get('event')
        if event_filter:
            registrations = registrations.filter(event__event_id=event_filter)

        role_filter = request.GET.get('role')
        if role_filter:
            registrations = registrations.filter(role__name=role_filter)

        type_filter = request.GET.get('type')
        if type_filter:
            registrations = registrations.filter(attendee_type__name=type_filter)

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="registrations.csv"'

        # Create CSV writer
        writer = csv.writer(response)
        writer.writerow([
            'Registration ID', 'Event', 'First Name', 'Last Name', 'Email',
            'Phone', 'Company', 'Role', 'Type', 'Status', 'Registered At'
        ])

        # Write data rows
        for registration in registrations:
            writer.writerow([
                registration.registration_id,
                registration.event.title,
                registration.user.first_name,
                registration.user.last_name,
                registration.user.email,
                registration.user.phone or '',
                registration.user.company or '',
                registration.role.name,
                registration.attendee_type.name if registration.attendee_type else '',
                registration.status,
                registration.registered_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error exporting registrations: {str(e)}'
        }, status=500)

@login_required
def speaker_guidelines_pdf(request):
    """
    Generate a PDF version of the speaker guidelines
    """
    # Prepare context for the PDF template
    context = {
        'now': timezone.now(),
    }

    # Render the template
    template = get_template('speaker/guidelines_pdf.html')
    html = template.render(context)

    # Create the PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="speaker_guidelines.pdf"'

    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('We had some errors generating the PDF: <pre>' + html + '</pre>')
    return response

@login_required
def sponsor_events(request):
    """
    View function for the sponsor's events dashboard.
    Shows all events sponsored by the current user's organization.
    """
    # Get current date
    today = timezone.now()

    # Get all events where the user's organization is a sponsor
    sponsored_events = Event.objects.filter(
        sponsors__user=request.user
    ).annotate(
        attendee_count=Count('registration', distinct=True),
        avg_rating=Avg('feedback__rating')
    ).distinct()

    # Get filter parameters
    time_filter = request.GET.get('time', 'all')
    tier_filter = request.GET.get('tier', '')
    view_type = request.GET.get('view', 'list')

    # Apply time filter
    if time_filter == 'active':
        sponsored_events = sponsored_events.filter(
            start_date__lte=today,
            end_date__gte=today
        )
    elif time_filter == 'upcoming':
        sponsored_events = sponsored_events.filter(start_date__gt=today)
    elif time_filter == 'past':
        sponsored_events = sponsored_events.filter(end_date__lt=today)

    # Apply tier filter
    if tier_filter:
        sponsored_events = sponsored_events.filter(sponsors__tier=tier_filter)

    # Calculate statistics
    total_events = sponsored_events.count()
    active_events = sponsored_events.filter(
        start_date__lte=today,
        end_date__gte=today
    ).count()
    total_attendees = sum(event.attendee_count for event in sponsored_events)
    avg_engagement = round((total_attendees / total_events) * 100) if total_events > 0 else 0

    # Prepare events for calendar view
    events_json = []
    if view_type == 'calendar':
        for event in sponsored_events:
            events_json.append({
                'title': event.title,
                'start': event.start_date.isoformat(),
                'end': event.end_date.isoformat(),
                'url': f'/events/{event.event_id}/',
                'backgroundColor': '#4e73df' if event.start_date > today else '#858796'
            })

    # Handle export requests
    if 'export' in request.GET:
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            # Generate PDF report
            return generate_sponsor_report_pdf(request, sponsored_events)
        elif export_format == 'excel':
            # Generate Excel report
            return generate_sponsor_report_excel(request, sponsored_events)

    # Calculate ROI and investment data
    total_investment = sum(event.sponsorship_amount for event in sponsored_events if event.sponsorship_amount)
    total_leads = sum(event.leads_generated for event in sponsored_events if event.leads_generated)
    roi = ((total_leads * 100) / total_investment) if total_investment > 0 else 0

    context = {
        'events': sponsored_events,
        'total_events': total_events,
        'active_events': active_events,
        'total_attendees': total_attendees,
        'avg_engagement': avg_engagement,
        'time_filter': time_filter,
        'tier_filter': tier_filter,
        'view_type': view_type,
        'events_json': json.dumps(events_json) if view_type == 'calendar' else [],
        'today_date': today.strftime('%B %d, %Y'),
        'upcoming_events': sponsored_events.filter(start_date__gt=today).order_by('start_date'),
        'total_investment': total_investment,
        'roi': roi
    }

    return render(request, 'sponsor/events.html', context)

def generate_sponsor_report_pdf(request, events):
    """Generate a PDF report of sponsored events."""
    # Implementation for PDF report generation
    pass

def generate_sponsor_report_excel(request, events):
    """Generate an Excel report of sponsored events."""
    # Implementation for Excel report generation
    pass

@login_required
def sponsor_profile(request):
    """View function for managing sponsor's company profile."""
    try:
        # Get or create sponsor profile for the current user
        sponsor_profile = SponsorProfile.objects.get(
            sponsorships__user=request.user
        )
    except SponsorProfile.DoesNotExist:
        sponsor_profile = None

    if request.method == 'POST':
        form = SponsorProfileForm(request.POST, request.FILES, instance=sponsor_profile)
        if form.is_valid():
            profile = form.save()
            messages.success(request, "Company profile updated successfully!")
            return redirect('sponsor_profile')
    else:
        form = SponsorProfileForm(instance=sponsor_profile)

    context = {
        'form': form,
        'profile': sponsor_profile
    }
    return render(request, 'sponsor/profile.html', context)

@login_required
def sponsor_analytics(request):
    """View function for sponsor's overall analytics dashboard."""
    # Get all events where the user's organization is a sponsor
    sponsored_events = Event.objects.filter(
        sponsors__user=request.user
    ).distinct()

    # Calculate overall statistics
    total_events = sponsored_events.count()
    total_attendees = sum(event.get_attendee_count() for event in sponsored_events)
    total_investment = sum(
        sponsor.sponsorship_amount 
        for event in sponsored_events 
        for sponsor in event.sponsors.filter(user=request.user)
    )
    avg_roi = calculate_sponsor_roi(request.user)

    # Get event performance metrics
    event_metrics = []
    for event in sponsored_events:
        metrics = {
            'event': event,
            'attendees': event.get_attendee_count(),
            'leads': event.get_sponsor_leads(request.user),
            'engagement': event.get_sponsor_engagement(request.user),
            'roi': calculate_event_roi(event, request.user)
        }
        event_metrics.append(metrics)

    context = {
        'total_events': total_events,
        'total_attendees': total_attendees,
        'total_investment': total_investment,
        'avg_roi': avg_roi,
        'event_metrics': event_metrics
    }
    return render(request, 'sponsor/analytics.html', context)

@login_required
def sponsor_event_analytics(request, event_id):
    """View function for sponsor's analytics for a specific event."""
    event = get_object_or_404(Event, event_id=event_id)
    
    # Verify the user is a sponsor for this event
    if not event.sponsors.filter(user=request.user).exists():
        messages.error(request, "You don't have permission to view analytics for this event.")
        return redirect('sponsor_events')

    # Get sponsor-specific metrics
    sponsor = event.sponsors.get(user=request.user)
    metrics = {
        'attendees': event.get_attendee_count(),
        'leads': event.get_sponsor_leads(request.user),
        'engagement': event.get_sponsor_engagement(request.user),
        'roi': calculate_event_roi(event, request.user),
        'booth_visits': event.get_sponsor_booth_visits(request.user),
        'material_downloads': event.get_sponsor_material_downloads(request.user),
        'contact_requests': event.get_sponsor_contact_requests(request.user)
    }

    context = {
        'event': event,
        'sponsor': sponsor,
        'metrics': metrics
    }
    return render(request, 'sponsor/event_analytics.html', context)

@login_required
def sponsor_materials(request):
    """View function for managing sponsor's marketing materials."""
    # Get all events where the user's organization is a sponsor
    sponsored_events = Event.objects.filter(
        sponsors__user=request.user
    ).distinct()

    # Get sponsor profile
    try:
        sponsor_profile = SponsorProfile.objects.get(
            sponsorships__user=request.user
        )
    except SponsorProfile.DoesNotExist:
        sponsor_profile = None

    if request.method == 'POST':
        if 'upload_company_materials' in request.POST:
            # Handle company-wide materials upload
            form = SponsorProfileForm(
                request.POST, 
                request.FILES, 
                instance=sponsor_profile
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Company materials updated successfully!")
                return redirect('sponsor_materials')
        elif 'upload_event_materials' in request.POST:
            # Handle event-specific materials upload
            event_id = request.POST.get('event_id')
            event = get_object_or_404(Event, event_id=event_id)
            sponsor = event.sponsors.get(user=request.user)
            
            if request.FILES:
                for file in request.FILES.getlist('materials'):
                    SponsorMaterial.objects.create(
                        sponsor=sponsor,
                        event=event,
                        file=file,
                        name=file.name
                    )
                messages.success(request, "Event materials uploaded successfully!")
            return redirect('sponsor_materials')

    context = {
        'sponsored_events': sponsored_events,
        'sponsor_profile': sponsor_profile
    }
    return render(request, 'sponsor/materials.html', context)

@login_required
def sponsor_event_materials(request, event_id):
    """View function for managing sponsor's materials for a specific event."""
    event = get_object_or_404(Event, event_id=event_id)
    
    # Verify the user is a sponsor for this event
    if not event.sponsors.filter(user=request.user).exists():
        messages.error(request, "You don't have permission to manage materials for this event.")
        return redirect('sponsor_materials')

    sponsor = event.sponsors.get(user=request.user)
    materials = SponsorMaterial.objects.filter(sponsor=sponsor, event=event)

    if request.method == 'POST':
        if 'upload_materials' in request.POST:
            if request.FILES:
                for file in request.FILES.getlist('materials'):
                    SponsorMaterial.objects.create(
                        sponsor=sponsor,
                        event=event,
                        file=file,
                        name=file.name
                    )
                messages.success(request, "Materials uploaded successfully!")
        elif 'delete_material' in request.POST:
            material_id = request.POST.get('material_id')
            material = get_object_or_404(SponsorMaterial, id=material_id, sponsor=sponsor)
            material.delete()
            messages.success(request, "Material deleted successfully!")
        return redirect('sponsor_event_materials', event_id=event_id)

    context = {
        'event': event,
        'sponsor': sponsor,
        'materials': materials
    }
    return render(request, 'sponsor/event_materials.html', context)

@login_required
def sponsor_settings(request):
    """View function for managing sponsor's settings."""
    # Get sponsor profile
    try:
        sponsor_profile = SponsorProfile.objects.get(
            sponsorships__user=request.user
        )
    except SponsorProfile.DoesNotExist:
        sponsor_profile = None

    if request.method == 'POST':
        if 'update_notifications' in request.POST:
            # Update notification preferences
            sponsor_profile.notification_preferences = {
                'event_updates': request.POST.get('event_updates') == 'on',
                'attendee_interactions': request.POST.get('attendee_interactions') == 'on',
                'analytics_reports': request.POST.get('analytics_reports') == 'on',
                'material_downloads': request.POST.get('material_downloads') == 'on'
            }
            sponsor_profile.save()
            messages.success(request, "Notification preferences updated successfully!")
        elif 'update_display' in request.POST:
            # Update display preferences
            sponsor_profile.display_preferences = {
                'show_logo': request.POST.get('show_logo') == 'on',
                'show_description': request.POST.get('show_description') == 'on',
                'show_contact': request.POST.get('show_contact') == 'on',
                'show_website': request.POST.get('show_website') == 'on'
            }
            sponsor_profile.save()
            messages.success(request, "Display preferences updated successfully!")
        return redirect('sponsor_settings')

    context = {
        'sponsor_profile': sponsor_profile,
        'notification_preferences': getattr(sponsor_profile, 'notification_preferences', {}),
        'display_preferences': getattr(sponsor_profile, 'display_preferences', {})
    }
    return render(request, 'sponsor/settings.html', context)

def calculate_sponsor_roi(user):
    """Helper function to calculate overall ROI for a sponsor."""
    sponsored_events = Event.objects.filter(sponsors__user=user)
    total_investment = sum(
        sponsor.sponsorship_amount 
        for event in sponsored_events 
        for sponsor in event.sponsors.filter(user=user)
    )
    total_leads = sum(
        event.get_sponsor_leads(user)
        for event in sponsored_events
    )
    return (total_leads * 100 / total_investment) if total_investment > 0 else 0

def calculate_event_roi(event, user):
    """Helper function to calculate ROI for a specific event."""
    sponsor = event.sponsors.get(user=user)
    investment = sponsor.sponsorship_amount
    leads = event.get_sponsor_leads(user)
    return (leads * 100 / investment) if investment > 0 else 0

def send_sponsor_confirmation_email(sponsor, request):
    """Helper function to send sponsor confirmation email."""
    subject = f'Sponsorship Confirmation - {sponsor.event.title}'
    context = {
        'sponsor_profile': sponsor.sponsor_profile,
        'event': sponsor.event,
        'tier': sponsor.tier,
        'sponsorship_amount': sponsor.sponsorship_amount,
        'request': request
    }

    html_message = render_to_string('emails/sponsor_confirmation.html', context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [sponsor.sponsor_profile.primary_contact_email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"Error sending sponsor confirmation email: {e}")
        return False

@login_required
def mark_notification_read(request, id):
    """API view to mark a notification as read"""
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=id, user=request.user)
            notification.mark_as_read()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required
def mark_all_notifications_read(request):
    """API view to mark all notifications as read"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

@login_required
def all_notifications(request):
    """View for displaying all notifications"""
    notifications = Notification.objects.filter(user=request.user)
    
    # Mark all as read if requested
    if request.GET.get('mark_read'):
        notifications.filter(is_read=False).update(is_read=True)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)
    
    context = {
        'notifications': notifications_page,
        'unread_count': notifications.filter(is_read=False).count(),
        'user_role': get_user_role(request.user)
    }
    
    return render(request, 'notifications/all_notifications.html', context)

def get_user_notifications(user):
    """Helper function to get user's notifications for the dropdown"""
    return {
        'notifications': Notification.objects.filter(user=user)[:5],  # Get latest 5 notifications
        'unread_count': Notification.objects.filter(user=user, is_read=False).count()
    }

@login_required
def cancel_registration(request, event_id):
    """Cancel a user's registration for an event"""
    try:
        event = Event.objects.get(event_id=event_id)
        registration = Registration.objects.get(event=event, user=request.user)
        
        # Check if event has already started
        if timezone.now() >= event.start_date:
            messages.error(request, "Cannot cancel registration after the event has started.")
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot cancel registration after the event has started.'
            }, status=400)
        
        # Update registration status to cancelled
        registration.status = 'cancelled'
        registration.save()
        
        messages.success(request, "Your registration has been cancelled successfully.")
        return JsonResponse({'status': 'success'})
        
    except (Event.DoesNotExist, Registration.DoesNotExist):
        messages.error(request, "Registration not found.")
        return JsonResponse({'status': 'error'}, status=404)

def generate_event_ticket(event, registration):
    """Generate a PDF ticket for an event"""
    # Generate QR code with detailed ticket information
    ticket_data = {
        'event': {
            'id': str(event.event_id),
            'title': event.title,
            'category': event.category.name,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat(),
            'location': event.location,
            'organizer': event.organizer.get_full_name()
        },
        'attendee': {
            'id': str(registration.user.user_id),
            'name': f"{registration.user.first_name} {registration.user.last_name}",
            'email': registration.user.email,
            'type': registration.attendee_type.name if registration.attendee_type else 'Standard'
        },
        'registration': {
            'id': str(registration.registration_id),
            'status': registration.status,
            'registered_at': registration.registered_at.isoformat(),
            'is_checked_in': registration.checked_in,
            'terms_agreed': registration.agreed_to_terms
        }
    }
    
    qr_code_base64 = generate_qr_code_base64(json.dumps(ticket_data))

    # Get the template
    template = get_template('ticket_pdf.html')
    
    # Prepare context
    context = {
        'event': event,
        'user': registration.user,
        'registration': registration,
        'qr_code': qr_code_base64,
        'base_url': settings.BASE_URL if hasattr(settings, 'BASE_URL') else ''
    }
    
    # Render template
    html = template.render(context)
    
    # Create PDF
    pdf_buffer = BytesIO()
    pisa.CreatePDF(html, dest=pdf_buffer)
    
    # Reset buffer position
    pdf_buffer.seek(0)
    return pdf_buffer

@login_required
def register_event_by_link(request, registration_link):
    """
    View function to handle event registration via custom registration link.
    """
    # Find the event by registration link
    event = get_object_or_404(Event, registration_link__endswith=registration_link)
    
    # Check if registration is enabled for this event
    if not event.enable_registration:
        messages.error(request, "Registration for this event is closed.")
        return redirect('event_detail', event_id=event.event_id)
    
    # Check if event has already started
    if timezone.now() >= event.start_date:
        messages.error(request, "Registration is closed. The event has already started.")
        return redirect('event_detail', event_id=event.event_id)
    
    # Check if the event is full
    if event.is_full():
        messages.error(request, "Sorry, this event has reached its maximum capacity.")
        return redirect('event_detail', event_id=event.event_id)
    
    # Check if user is already registered
    if Registration.objects.filter(event=event, user=request.user).exists():
        messages.warning(request, "You are already registered for this event.")
        return redirect('event_detail', event_id=event.event_id)
    
    if request.method == 'POST':
        # Update user profile with form data
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', '')
        user.organization = request.POST.get('organization', '')
        user.designation = request.POST.get('designation', '')
        user.save()

        try:
            # Get the attendee type by ID
            attendee_type = AttendeeType.objects.get(type_id=request.POST.get('attendee_type'))
            
            # Create registration
            registration = Registration.objects.create(
                user=user,
                event=event,
                role=ParticipantRole.objects.get(name='attendee'),
                attendee_type=attendee_type,
                dietary_requirements=request.POST.get('dietary_requirements', ''),
                special_assistance=request.POST.get('special_assistance', ''),
                reminders_enabled=request.POST.get('reminders_enabled') == 'on',
                updates_enabled=request.POST.get('updates_enabled') == 'on',
                agreed_to_terms=True
            )
            
            # Send confirmation email
            send_registration_confirmation(request, registration)
            
            messages.success(request, "You have successfully registered for this event!")
            return redirect('event_detail', event_id=event.event_id)
            
        except AttendeeType.DoesNotExist:
            messages.error(request, "Invalid attendee type selected.")
            return redirect('register_event_by_link', registration_link=registration_link)
        except Exception as e:
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return redirect('register_event_by_link', registration_link=registration_link)
    
    # Get all attendee types for the form
    attendee_types = AttendeeType.objects.all()
    
    context = {
        'event': event,
        'user': request.user,
        'attendee_types': attendee_types,
    }
    return render(request, 'event_registration_form.html', context)

def generate_ticket_qr(event, registration):
    """Generate QR code with enhanced ticket information"""
    # Create a validation hash
    validation_string = f"{registration.registration_id}:{event.event_id}:{registration.user.email}"
    validation_hash = hashlib.sha256(validation_string.encode()).hexdigest()[:8]  # Using first 8 chars for brevity

    # Format the data in a more concise way
    ticket_info = f"""🎫 {event.title}
📅 {event.start_date.strftime('%d %b %Y')}
⏰ {event.start_date.strftime('%I:%M %p')}
📍 {event.location}
👤 {registration.user.get_full_name()}
🎟️ {registration.attendee_type.name if registration.attendee_type else 'Standard'}

ID: {str(registration.registration_id)[:8]}...
VC: {validation_hash}"""

    # Create QR code instance with high error correction
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    # Add the formatted text data
    qr.add_data(ticket_info)
    qr.make(fit=True)
    
    # Create QR code image with good contrast
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_image = base64.b64encode(buffer.getvalue()).decode()
    
    return qr_image

def generate_event_qr(event, request):
    """Generate QR code for event details"""
    try:
        current_site = get_current_site(request)
        event_url = f"https://{current_site.domain}{reverse('event_detail', args=[event.event_id])}"
        
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Add event details to QR code
        qr_data = f"""
Event: {event.title}
Date: {event.start_date.strftime('%B %d, %Y %I:%M %p')}
Location: {event.location}
Register: {event_url}
"""
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert image to base64 for email embedding
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_image = base64.b64encode(buffer.getvalue()).decode()
        
        return qr_image
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return None

def generate_social_share_links(event, request):
    """Generate social media sharing links"""
    current_site = get_current_site(request)
    event_url = f"https://{current_site.domain}{reverse('event_detail', args=[event.event_id])}"
    
    # URL encode the text
    from urllib.parse import quote
    title = quote(event.title)
    description = quote(f"Join us at {event.title} on {event.start_date.strftime('%B %d, %Y')}")
    
    return {
        'facebook': f"https://www.facebook.com/sharer/sharer.php?u={quote(event_url)}",
        'twitter': f"https://twitter.com/intent/tweet?text={description}&url={quote(event_url)}",
        'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?url={quote(event_url)}",
        'whatsapp': f"https://wa.me/?text={description}%20{quote(event_url)}"
    }
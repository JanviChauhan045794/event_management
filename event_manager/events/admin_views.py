from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.html import format_html
import json
import csv
from datetime import datetime, timedelta
from io import StringIO
from django.contrib.auth.hashers import make_password

from .models import (
    User, Event, Registration, Feedback, Speaker, Sponsor,
    CheckIn, Revenue, SiteSettings, BlogPost, ContactMessage,
    BlogCategory, ContactInformation, AdminDashboardSettings,
    ParticipantRole, EventCategory
)

def is_admin(user):
    """Check if user is an admin"""
    return user.is_authenticated and user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard view"""
    # Get dashboard settings for the user
    dashboard_settings, created = AdminDashboardSettings.objects.get_or_create(
        user=request.user,
        defaults={
            'dashboard_theme': 'light',
            'items_per_page': 10,
            'show_revenue_stats': True,
            'show_user_stats': True,
            'show_event_stats': True
        }
    )

    # Get counts for dashboard stats
    total_users = User.objects.count()
    total_events = Event.objects.count()
    total_registrations = Registration.objects.count()
    total_revenue = Revenue.objects.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0

    # Get recent users
    recent_users = User.objects.order_by('-date_joined')[:5]

    # Get upcoming events
    upcoming_events = Event.objects.filter(
        start_date__gte=timezone.now()
    ).order_by('start_date')[:5]

    # Get recent feedback
    recent_feedback = Feedback.objects.select_related('event', 'user').order_by('-feedback_id')[:5]

    # Get pending speakers for approval
    pending_speakers = Registration.objects.filter(
        role__name='speaker',
        user__is_staff=False
    ).select_related('user', 'event').order_by('-registered_at')[:5]

    # Get recent contact messages
    recent_messages = ContactMessage.objects.filter(status='new').order_by('-created_at')[:5]

    context = {
        'total_users': total_users,
        'total_events': total_events,
        'total_registrations': total_registrations,
        'total_revenue': total_revenue,
        'recent_users': recent_users,
        'upcoming_events': upcoming_events,
        'recent_feedback': recent_feedback,
        'pending_speakers': pending_speakers,
        'recent_messages': recent_messages,
        'dashboard_settings': dashboard_settings,
        'section': 'dashboard'
    }

    return render(request, 'admin_dashboard/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def admin_users(request):
    """Admin users management view"""
    # Get filter parameters
    user_type = request.GET.get('user_type', '')
    role = request.GET.get('role', '')
    is_active = request.GET.get('is_active', '')
    search_query = request.GET.get('q', '')

    # Base queryset
    users = User.objects.all().order_by('-date_joined')

    # Apply filters
    if user_type:
        users = users.filter(user_type=user_type)

    if role:
        users = users.filter(registration__role__name=role).distinct()

    if is_active:
        is_active_bool = is_active == 'true'
        users = users.filter(is_active=is_active_bool)

    if search_query:
        users = users.filter(
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(company__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'user_types': User.USER_TYPES,
        'section': 'users',
        'filters': {
            'user_type': user_type,
            'role': role,
            'is_active': is_active,
            'q': search_query
        }
    }

    return render(request, 'admin_dashboard/users.html', context)

@login_required
@user_passes_test(is_admin)
def admin_events(request):
    """Admin events management view"""
    # Get filter parameters
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    search_query = request.GET.get('q', '')

    # Base queryset
    events = Event.objects.all().select_related('category', 'organizer').order_by('-start_date')

    # Apply filters
    if category:
        events = events.filter(category__category_id=category)

    if status:
        now = timezone.now()
        if status == 'upcoming':
            events = events.filter(start_date__gt=now)
        elif status == 'ongoing':
            events = events.filter(start_date__lte=now, end_date__gte=now)
        elif status == 'past':
            events = events.filter(end_date__lt=now)

    if search_query:
        events = events.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(organizer__email__icontains=search_query)
        )

    # Get all categories for the filter dropdown
    categories = EventCategory.objects.all()

    # Pagination
    paginator = Paginator(events, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'events': page_obj,
        'categories': list(categories),
        'section': 'events',
        'filters': {
            'category': category,
            'status': status,
            'q': search_query
        }
    }

    return render(request, 'admin_dashboard/events.html', context)

@login_required
@user_passes_test(is_admin)
def admin_speakers(request):
    """Admin speakers management view"""
    # Check if this is a speaker approval request
    if '_approve_speaker' in request.GET and 'user_id' in request.GET:
        user_id = request.GET.get('user_id')
        try:
            user = User.objects.get(user_id=user_id)

            # Get the speaker role
            try:
                speaker_role = ParticipantRole.objects.get(name='speaker')
            except ParticipantRole.DoesNotExist:
                # Create the speaker role if it doesn't exist
                speaker_role = ParticipantRole.objects.create(name='speaker')

            # Create a Speaker object if it doesn't exist
            speaker, created = Speaker.objects.get_or_create(
                user=user,
                defaults={'bio': f"Bio for {user.get_full_name() or user.email}"}
            )

            # Update user status
            user.is_staff = True
            user.save()

            # Get the registration for this speaker
            registration = Registration.objects.filter(
                user=user,
                role__name='speaker'
            ).first()

            # If no registration exists, create one for a default event
            if not registration:
                # Get or create a default event
                default_category, _ = EventCategory.objects.get_or_create(name='Default')
                default_event, _ = Event.objects.get_or_create(
                    title='Speaker Approval',
                    defaults={
                        'description': 'Default event for speaker approval',
                        'category': default_category,
                        'organizer': request.user,
                        'start_date': timezone.now(),
                        'end_date': timezone.now() + timedelta(days=30)
                    }
                )

                # Create a registration for the speaker
                registration = Registration.objects.create(
                    event=default_event,
                    user=user,
                    role=speaker_role
                )

            # Create a notification for the speaker
            if registration and registration.event:
                from events.views import create_notification

                create_notification(
                    user=user,
                    event=registration.event,
                    notification_type='speaker_approved',
                    title='Speaker Status Approved',
                    message=f"Your speaker status for '{registration.event.title}' has been approved. You can now access the speaker dashboard.",
                    icon='fa-check-circle',
                    color='success',
                    action_url='/events/dashboard/speaker/'
                )

                # Send email notification
                from django.core.mail import send_mail
                from django.template.loader import render_to_string
                from django.utils.html import strip_tags
                from django.conf import settings

                subject = 'Speaker Status Approved'
                context = {
                    'user': user,
                    'event': registration.event,
                    'dashboard_url': f"{request.scheme}://{request.get_host()}/events/dashboard/speaker/"
                }

                html_message = render_to_string('emails/speaker_approved.html', context)
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        html_message=html_message,
                        fail_silently=False
                    )
                except Exception as e:
                    # Log the error but don't stop the process
                    print(f"Error sending email: {str(e)}")

            messages.success(request, f"Speaker {user.get_full_name() or user.email} has been approved successfully.")
            return redirect('admin_speakers')
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('admin_speakers')

    # Get all speakers
    speakers = Speaker.objects.all().select_related('user')

    # Get pending speaker approvals - exclude users who are already staff (approved)
    pending_approvals = Registration.objects.filter(
        role__name='speaker',
        user__is_staff=False
    ).select_related('user', 'event').order_by('-registered_at')

    # Ensure we're not showing any approved speakers in the pending list
    # This is a double-check in case the is_staff flag wasn't properly set
    approved_speaker_users = Speaker.objects.values_list('user_id', flat=True)
    pending_approvals = pending_approvals.exclude(user__user_id__in=approved_speaker_users)

    context = {
        'speakers': speakers,
        'pending_approvals': pending_approvals,
        'section': 'speakers'
    }

    return render(request, 'admin_dashboard/speakers.html', context)

@login_required
@user_passes_test(is_admin)
def admin_revenue(request):
    """Admin revenue tracking view"""
    # Get all events with revenue data
    events_with_revenue = Event.objects.filter(revenues__isnull=False).distinct()

    # Get events without revenue data
    events_without_revenue = Event.objects.filter(revenues__isnull=True)

    # Calculate total revenue
    total_revenue = Revenue.objects.aggregate(Sum('total_revenue'))['total_revenue__sum'] or 0
    total_expenses = Revenue.objects.aggregate(Sum('expenses'))['expenses__sum'] or 0
    total_profit = Revenue.objects.aggregate(Sum('net_profit'))['net_profit__sum'] or 0

    context = {
        'events_with_revenue': events_with_revenue,
        'events_without_revenue': events_without_revenue,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'section': 'revenue'
    }

    return render(request, 'admin_dashboard/revenue.html', context)

@login_required
@user_passes_test(is_admin)
def admin_checkins(request):
    """Admin check-ins management view"""
    # Get all check-ins
    checkins = CheckIn.objects.all().select_related(
        'registration', 'registration__user', 'registration__event', 'checked_in_by'
    ).order_by('-checked_in_at')

    # Pagination
    paginator = Paginator(checkins, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'checkins': page_obj,
        'section': 'checkins'
    }

    return render(request, 'admin_dashboard/checkins.html', context)

@login_required
@user_passes_test(is_admin)
def admin_site_settings(request):
    """Admin site settings view"""
    # Get or create site settings
    site_settings, created = SiteSettings.objects.get_or_create(
        pk=SiteSettings.objects.first().pk if SiteSettings.objects.exists() else None,
        defaults={
            'site_name': 'CorpEventX',
            'footer_text': '© 2025 CorpEventX. All rights reserved.'
        }
    )

    # Get or create contact information
    contact_info, created = ContactInformation.objects.get_or_create(
        pk=ContactInformation.objects.first().pk if ContactInformation.objects.exists() else None,
        defaults={
            'email': 'contact@corpeventx.com',
            'phone': '(555) 123-4567'
        }
    )

    context = {
        'site_settings': site_settings,
        'contact_info': contact_info,
        'section': 'settings'
    }

    return render(request, 'admin_dashboard/site_settings.html', context)

@login_required
@user_passes_test(is_admin)
def admin_blog(request):
    """Admin blog management view"""
    # Get all blog posts
    posts = BlogPost.objects.all().select_related('author', 'category').order_by('-created_at')

    # Get all categories
    categories = BlogCategory.objects.all()

    # Pagination
    paginator = Paginator(posts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'posts': page_obj,
        'categories': categories,
        'section': 'blog'
    }

    return render(request, 'admin_dashboard/blog.html', context)

@login_required
@user_passes_test(is_admin)
def admin_contact_messages(request):
    """Admin contact messages view"""
    # Get all contact messages
    messages_list = ContactMessage.objects.all().order_by('-created_at')

    # Pagination
    paginator = Paginator(messages_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'messages': page_obj,
        'section': 'contact'
    }

    return render(request, 'admin_dashboard/contact_messages.html', context)

@login_required
@user_passes_test(is_admin)
def admin_feedback(request):
    """Admin feedback management view"""
    # Get filter parameters
    event_filter = request.GET.get('event', '')
    rating_filter = request.GET.get('rating', '')
    search_query = request.GET.get('q', '')

    # Base queryset
    feedback_list = Feedback.objects.all().select_related('event', 'user').order_by('-feedback_id')

    # Apply filters
    if event_filter:
        feedback_list = feedback_list.filter(event__event_id=event_filter)

    if rating_filter and rating_filter.isdigit():
        feedback_list = feedback_list.filter(rating=int(rating_filter))

    if search_query:
        feedback_list = feedback_list.filter(
            Q(comments__icontains=search_query) |
            Q(event__title__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )

    # Get all events for the filter dropdown
    events = Event.objects.all().order_by('title')

    # Calculate statistics
    total_feedback = feedback_list.count()
    avg_rating = feedback_list.aggregate(Avg('rating'))['rating__avg'] or 0

    # Rating distribution
    rating_counts = {
        '5': feedback_list.filter(rating=5).count(),
        '4': feedback_list.filter(rating=4).count(),
        '3': feedback_list.filter(rating=3).count(),
        '2': feedback_list.filter(rating=2).count(),
        '1': feedback_list.filter(rating=1).count(),
    }

    # Ensure all keys are present even if they're strings
    for i in range(1, 6):
        rating_counts.setdefault(str(i), 0)

    # Calculate percentages
    rating_distribution = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}  # Initialize with all ratings
    if total_feedback > 0:
        for rating, count in rating_counts.items():
            rating_distribution[rating] = round((count / total_feedback) * 100)

    # Get top rated events
    top_rated_events = Event.objects.annotate(
        avg_rating=Avg('feedback__rating'),
        feedback_count=Count('feedback')
    ).filter(feedback_count__gt=0).order_by('-avg_rating')[:5]

    # Pagination
    paginator = Paginator(feedback_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'feedback_list': page_obj,
        'events': events,
        'total_feedback': total_feedback,
        'avg_rating': avg_rating,
        'rating_counts': rating_counts,
        'rating_distribution': rating_distribution,
        'top_rated_events': top_rated_events,
        'filters': {
            'event': event_filter,
            'rating': rating_filter,
            'q': search_query
        },
        'section': 'feedback'
    }

    return render(request, 'admin_dashboard/feedback.html', context)

@login_required
@user_passes_test(is_admin)
def add_user(request):
    """Add a regular user"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        user_type = request.POST.get('user_type')
        
        try:
            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                user_type=user_type,
                is_staff=False,
                is_superuser=False
            )
            user.set_password(password)
            user.save()
            messages.success(request, f'User {email} created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
        
        return redirect('admin_users')
    
    context = {
        'user_types': User.USER_TYPES,
        'section': 'users'
    }
    return render(request, 'admin_dashboard/add_user.html', context)

@login_required
@user_passes_test(is_admin)
def add_admin(request):
    """Add an admin user"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                user_type='admin',
                is_staff=True,
                is_superuser=True
            )
            user.set_password(password)
            user.save()
            messages.success(request, f'Admin user {email} created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating admin user: {str(e)}')
        
        return redirect('admin_users')
    
    context = {
        'section': 'users'
    }
    return render(request, 'admin_dashboard/add_admin.html', context)

@login_required
@user_passes_test(is_admin)
def import_users(request):
    """Import users from CSV file"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return redirect('admin_users')
        
        decoded_file = csv_file.read().decode('utf-8')
        csv_data = csv.DictReader(StringIO(decoded_file))
        
        success_count = 0
        error_count = 0
        
        for row in csv_data:
            try:
                user = User.objects.create(
                    email=row['email'],
                    first_name=row.get('first_name', ''),
                    last_name=row.get('last_name', ''),
                    user_type=row.get('user_type', 'employee'),
                    is_staff=row.get('is_staff', '').lower() == 'true',
                    is_superuser=row.get('is_superuser', '').lower() == 'true'
                )
                user.set_password(row.get('password', 'changeme123'))
                user.save()
                success_count += 1
            except Exception as e:
                error_count += 1
                continue
        
        messages.success(request, f'Successfully imported {success_count} users. {error_count} failed.')
        return redirect('admin_users')
    
    return render(request, 'admin_dashboard/import_users.html', {'section': 'users'})

@login_required
@user_passes_test(is_admin)
def export_users(request):
    """Export users to CSV file"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Email', 'First Name', 'Last Name', 'User Type', 'Is Staff', 'Is Active', 'Date Joined'])
    
    users = User.objects.all().values_list(
        'email', 'first_name', 'last_name', 'user_type', 'is_staff', 'is_active', 'date_joined'
    )
    for user in users:
        writer.writerow(user)
    
    return response

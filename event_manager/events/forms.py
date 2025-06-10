from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, AttendeeType, ParticipantRole, Event, Speaker, EventSpeaker, SponsorTier, SponsorProfile, Sponsor, EventTag

class CustomUserCreationForm(UserCreationForm):
    """
    A form for creating a new user with all required fields.
    """
    # Remove username field since we're using email as username
    username = None

    # Add fields that match the User model
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    company = forms.CharField(max_length=100, required=False)
    user_type = forms.ChoiceField(choices=User.USER_TYPES, required=True)
    role = forms.ChoiceField(choices=[], required=True)  # Will be populated in __init__
    attendee_type = forms.ChoiceField(choices=[], required=False)  # Will be populated in __init__

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'company', 'user_type', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Remove password validation against username (email)
        self.fields['password1'].help_text = "Password must be at least 8 characters long."

        # Remove the UserAttributeSimilarityValidator
        for validator in self.fields['password1'].validators:
            if validator.__class__.__name__ == 'UserAttributeSimilarityValidator':
                self.fields['password1'].validators.remove(validator)

        # Populate role choices from database
        roles = ParticipantRole.objects.all()
        if not roles.exists():
            # Create default roles if none exist
            roles = [
                ParticipantRole.objects.create(name='attendee'),
                ParticipantRole.objects.create(name='speaker'),
                ParticipantRole.objects.create(name='organizer'),
            ]

        self.fields['role'].choices = [(role.name, role.name.title()) for role in roles]

        # Populate attendee type choices from database
        attendee_types = AttendeeType.objects.all()
        if not attendee_types.exists():
            # Create default attendee types if none exist
            attendee_types = [
                AttendeeType.objects.create(name='student'),
                AttendeeType.objects.create(name='professional'),
                AttendeeType.objects.create(name='academic'),
                AttendeeType.objects.create(name='other'),
            ]

        self.fields['attendee_type'].choices = [(type.name, type.name.title()) for type in attendee_types]

        # Make email field required and unique
        self.fields['email'].required = True
        self.fields['email'].unique = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return password1

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        attendee_type = cleaned_data.get('attendee_type')

        # If role is attendee, attendee_type is required
        if role == 'attendee' and not attendee_type:
            self.add_error('attendee_type', 'Attendee type is required for attendees.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        user.company = self.cleaned_data['company']
        user.user_type = self.cleaned_data['user_type']

        if commit:
            user.save()

        return user

class EventRegistrationForm(forms.Form):
    """
    Form for attendees to register for an event
    """
    # Personal information fields
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company/Organization'})
    )

    # Attendee type selection
    attendee_type = forms.ModelChoiceField(
        queryset=AttendeeType.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Special requirements
    dietary_requirements = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Any dietary requirements?'})
    )
    special_assistance = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Do you need any special assistance?'})
    )

    # Notification preferences
    reminders_enabled = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    updates_enabled = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Terms and conditions
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(EventRegistrationForm, self).__init__(*args, **kwargs)

        # Pre-fill form with user data if available
        if user and user.is_authenticated:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = user.phone
            self.fields['company'].initial = user.company


class SponsorProfileForm(forms.ModelForm):
    """
    Form for creating and editing sponsor profiles
    """
    class Meta:
        model = SponsorProfile
        fields = [
            'company_name', 'company_description', 'website', 'industry', 'company_size',
            'primary_contact_name', 'primary_contact_email', 'primary_contact_phone', 'primary_contact_title',
            'secondary_contact_name', 'secondary_contact_email', 'secondary_contact_phone', 'secondary_contact_title',
            'address_line1', 'address_line2', 'city', 'state_province', 'postal_code', 'country',
            'logo', 'banner_image', 'marketing_materials', 'notes', 'special_requirements'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'company_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Brief description of the company'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.company.com'}),
            'industry': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Technology, Healthcare'}),
            'company_size': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('', 'Select company size'),
                ('1-10', '1-10 employees'),
                ('11-50', '11-50 employees'),
                ('51-200', '51-200 employees'),
                ('201-500', '201-500 employees'),
                ('501-1000', '501-1000 employees'),
                ('1000+', '1000+ employees'),
            ]),
            'primary_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primary Contact Name'}),
            'primary_contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@company.com'}),
            'primary_contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 123-4567'}),
            'primary_contact_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'secondary_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Secondary Contact Name'}),
            'secondary_contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'secondary@company.com'}),
            'secondary_contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 123-4567'}),
            'secondary_contact_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street Address'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apartment, suite, etc.'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state_province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State/Province'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal Code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'banner_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'marketing_materials': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal notes about the sponsor'}),
            'special_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Special requirements or requests'}),
        }


class SponsorTierForm(forms.ModelForm):
    """
    Form for creating and editing sponsor tiers
    """
    class Meta:
        model = SponsorTier
        fields = [
            'name', 'display_order', 'color_code', 'base_price',
            'logo_placement', 'booth_space', 'speaking_opportunities', 'networking_access',
            'marketing_materials', 'social_media_mentions', 'email_mentions'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Platinum, Gold, Silver'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1'}),
            'color_code': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'logo_placement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Main stage backdrop, Website header'}),
            'booth_space': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 10x10 booth, Premium location'}),
            'speaking_opportunities': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'networking_access': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'marketing_materials': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'social_media_mentions': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'email_mentions': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        }


class SponsorForm(forms.ModelForm):
    """
    Form for creating event sponsorships
    """
    class Meta:
        model = Sponsor
        fields = [
            'sponsor_profile', 'tier', 'sponsorship_amount', 'contract_signed',
            'contract_date', 'payment_received', 'payment_date', 'status'
        ]
        widgets = {
            'sponsor_profile': forms.Select(attrs={'class': 'form-control'}),
            'tier': forms.Select(attrs={'class': 'form-control'}),
            'sponsorship_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'contract_signed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contract_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_received': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super(SponsorForm, self).__init__(*args, **kwargs)

        # Filter sponsor profiles to exclude those already sponsoring this event
        if event:
            existing_sponsors = Sponsor.objects.filter(event=event).values_list('sponsor_profile_id', flat=True)
            self.fields['sponsor_profile'].queryset = SponsorProfile.objects.exclude(
                profile_id__in=existing_sponsors
            ).filter(is_active=True)


class EventForm(forms.ModelForm):
    """
    Form for creating and editing events
    """
    # Format the date and time fields nicely
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Select the start date and time of the event"
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Select the end date and time of the event"
    )

    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        help_text="Provide a detailed description of the event"
    )

    # Add tags field (multiple selection)
    tags = forms.ModelMultipleChoiceField(
        queryset=EventTag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select relevant tags'
        }),
        help_text="Select tags that describe your event (e.g., AI, DevOps, Cloud Computing)"
    )

    # Add speakers field (multiple selection)
    speakers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(registration__role__name='speaker').distinct(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        help_text="Select one or more speakers for this event"
    )

    # Add speaker topics field (for multiple speakers)
    speaker_topics = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter topics for each speaker, one per line'}),
        help_text="Optionally provide topics for each selected speaker (one per line)"
    )

    # Add keynote speaker field
    keynote_speaker = forms.ModelChoiceField(
        queryset=User.objects.filter(registration__role__name='speaker').distinct(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2'}),
        help_text="Select a keynote speaker for this event (optional)"
    )

    # Add rulebook field
    rulebook = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'accept': '.pdf'}),
        help_text="Upload an optional rulebook PDF for this event"
    )

    # Add capacity field
    capacity = forms.IntegerField(
        min_value=1,
        initial=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Maximum number of attendees allowed for this event"
    )

    # Add enable_registration field
    enable_registration = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Allow users to register for this event"
    )

    # Add custom registration link field
    custom_registration_link = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_custom_registration_link'}),
        help_text="Use a custom registration link instead of the auto-generated one"
    )

    # Add notify speakers field
    notify_speakers = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Send email notifications to assigned speakers"
    )

    class Meta:
        model = Event
        fields = ('title', 'description', 'category', 'tags', 'start_date', 'end_date',
                  'location', 'banner', 'ticket_price', 'rulebook', 'capacity',
                  'enable_registration', 'registration_link')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Event Title', 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'Event Location', 'class': 'form-control'}),
            'ticket_price': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'banner': forms.FileInput(attrs={'class': 'form-control-file', 'accept': 'image/*'}),
            'registration_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/register'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get all users with speaker role
        speaker_users = User.objects.filter(registration__role__name='speaker').distinct()

        # Update the queryset for speakers and keynote_speaker fields
        self.fields['speakers'].queryset = speaker_users
        self.fields['keynote_speaker'].queryset = speaker_users

        # If this is an edit form (instance exists)
        if self.instance and self.instance.pk:
            # Get existing speakers for this event
            event_speakers = EventSpeaker.objects.filter(event=self.instance)

            # Set initial values for speakers field
            speaker_users_ids = event_speakers.values_list('speaker__user__user_id', flat=True)
            self.fields['speakers'].initial = speaker_users_ids

            # Set initial value for keynote speaker
            keynote = event_speakers.filter(is_keynote=True).first()
            if keynote:
                self.fields['keynote_speaker'].initial = keynote.speaker.user.user_id

            # Set initial value for speaker topics
            topics = []
            for es in event_speakers:
                if es.topic:
                    topics.append(f"{es.speaker.user.get_full_name()}: {es.topic}")

            if topics:
                self.fields['speaker_topics'].initial = "\n".join(topics)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        speakers = cleaned_data.get('speakers')
        keynote_speaker = cleaned_data.get('keynote_speaker')

        # Ensure end date is after start date
        if start_date and end_date and end_date <= start_date:
            raise forms.ValidationError("End date must be after start date")

        # Ensure keynote speaker is in the speakers list
        if keynote_speaker and speakers and keynote_speaker not in speakers:
            cleaned_data['speakers'] = list(speakers) + [keynote_speaker]

        return cleaned_data


class AdminUserCreationForm(UserCreationForm):
    """
    A form for creating admin users with all required fields.
    """
    # Remove username field since we're using email as username
    username = None

    # Add fields that match the User model
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    company = forms.CharField(max_length=100, required=False)

    # Admin-specific fields
    is_staff = forms.BooleanField(initial=True, required=False,
                                 help_text="Designates whether the user can log into the admin site.")
    is_superuser = forms.BooleanField(initial=False, required=False,
                                     help_text="Designates that this user has all permissions without explicitly assigning them.")

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'company',
                  'is_staff', 'is_superuser', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Remove password validation against username (email)
        self.fields['password1'].help_text = "Password must be at least 8 characters long."

        # Remove the UserAttributeSimilarityValidator
        for validator in self.fields['password1'].validators:
            if validator.__class__.__name__ == 'UserAttributeSimilarityValidator':
                self.fields['password1'].validators.remove(validator)

        # Make email field required and unique
        self.fields['email'].required = True
        self.fields['email'].unique = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return password1

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        user.company = self.cleaned_data['company']
        user.user_type = 'admin'  # Always set user_type to admin
        user.is_staff = self.cleaned_data['is_staff']
        user.is_superuser = self.cleaned_data['is_superuser']

        if commit:
            user.save()

        return user
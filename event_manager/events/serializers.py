from rest_framework import serializers
from .models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'email', 'user_type']

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'

class HackathonTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = HackathonTeam
        fields = '__all__'

class PaperSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperSubmission
        fields = '__all__'

# Add serializers for other models similarly
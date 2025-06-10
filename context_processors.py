from .events.views import get_user_notifications

def user_notifications(request):
    """Add notifications to template context"""
    if request.user.is_authenticated:
        return {'user_notifications': get_user_notifications(request.user)}
    return {'user_notifications': {'notifications': [], 'unread_count': 0}} 
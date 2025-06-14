"""
URL configuration for event_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add a import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from events.views import (
    index, user_type_selection, register, register_submit, registration_success, 
    login_view, dashboard_redirect, logout_view, event_admin, event_admin_submit
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('user-type-selection/', user_type_selection, name='user_type_selection'),
    path('register/', register, name='register'),
    path('register/submit/', register_submit, name='register_submit'),
    path('registration-success/', registration_success, name='registration_success'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_redirect, name='dashboard'),
    path('events/', include('events.urls')),
    path('event-admin/', event_admin, name='event_admin'),
    path('event-admin/submit/', event_admin_submit, name='event_admin_submit'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

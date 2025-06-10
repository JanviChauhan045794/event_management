from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.http import JsonResponse

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            # Return success response with role
            return JsonResponse({
                'success': True,
                'role': user.role
            })
        else:
            # Return validation errors
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return render(request, 'register.html')
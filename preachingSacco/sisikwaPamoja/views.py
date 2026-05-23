import re
from .counties import KENYA_COUNTIES
import json
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from .models import CustomUser, MemberProfile

def home_view(request):
    return render(request, 'sisikwaPamoja/home.html')

def _dashboard_redirect(user):
    if getattr(user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')
    return redirect('member_dashboard')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        middle_name = request.POST.get('middle_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')
        national_id = request.POST.get('national_id')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        county_of_birth = request.POST.get('county') or request.POST.get('county_of_birth')
        sub_county_of_birth = request.POST.get('sub_county') or request.POST.get('sub_county_of_birth')
        physical_address = request.POST.get('physical_address')
        marital_status = request.POST.get('marital_status')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        passport_photo = request.FILES.get('passport_photo')
        id_copy = request.FILES.get('id_copy')
   
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')
        
        
        if len(password1) < 8:
            messages.error(request, 
              'Password must be at least 8 characters.')
            return redirect('register')

        if not re.search(r'[A-Z]', password1):
            messages.error(request, 
               'Password must contain an uppercase letter.')
            return redirect('register')

        if not re.search(r'[a-z]', password1):
            messages.error(request, 
              'Password must contain a lowercase letter.')
            return redirect('register')

        if not re.search(r'[0-9]', password1):
             messages.error(request, 
                'Password must contain a number.')
             return redirect('register')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')
        
        if MemberProfile.objects.filter(national_id=national_id).exists():
            messages.error(request, 'National ID already registered.')
            return redirect('register')

        with transaction.atomic():
            user = CustomUser.objects.create_user(
                username=national_id,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role='member'
            )

            MemberProfile.objects.create(
                user=user,
                middle_name=middle_name,
                gender=gender,
                date_of_birth=date_of_birth,
                national_id=national_id,
                phone_number=phone_number,
                county=county_of_birth,
                sub_county=sub_county_of_birth,
                physical_address=physical_address,
                marital_status=marital_status,
                passport_photo=passport_photo,
                id_copy=id_copy,
                contribution_amount=0,
                member_type='last_expense'
            )

        # Send welcome email
        try:
            email_subject = render_to_string(
                'sisikwaPamoja/registration_email_subject.txt',
                {'user': user}
            ).strip()
            email_body = render_to_string(
                'sisikwaPamoja/registration_email.html',
                {'user': user}
            )
            
            email_message = EmailMessage(
                subject=email_subject,
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            email_message.send()
        except Exception as e:
            print(f"Error sending registration email: {e}")

        messages.success(request, 
            'Account created! You can now log in.')
        return redirect('login')

    return render(request, 
        'sisikwaPamoja/register.html',
        {'counties': json.dumps (KENYA_COUNTIES)}
        )


def login_view(request):
    if request.user.is_authenticated:
        return _dashboard_redirect(request.user)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, 
            username=username, password=password)

        if user is not None:
            login(request, user)
            return _dashboard_redirect(user)
        else:
            messages.error(request, 
                'Invalid username or password.')
            return redirect('login')

    return render(request, 
        'sisikwaPamoja/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def forgot_password_view(request):
    if request.user.is_authenticated:
        return _dashboard_redirect(request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        if CustomUser.objects.filter(email=email).exists():
            messages.success(request,
                'Password reset link sent to your email.')
        else:
            messages.error(request,
                'No account found with that email.')
        return redirect('forgot_password')

    return render(request,
        'sisikwaPamoja/forgot_password.html')

@login_required
def member_dashboard(request):
    if getattr(request.user, 'role', None) != 'member':
        return _dashboard_redirect(request.user)

    profile = MemberProfile.objects.filter(user=request.user).first()
    return render(request,
        'sisikwaPamoja/dashboard_member.html', {
            'profile': profile,
        })


@login_required
def admin_dashboard(request):
    if getattr(request.user, 'role', None) not in ('superadmin', 'staff'):
        return _dashboard_redirect(request.user)

    total_members = MemberProfile.objects.count()
    return render(request,
        'sisikwaPamoja/dashboard_admin.html', {
            'total_members': total_members
        })

@login_required
def delete_account(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user

        # Verify password before deleting
        if user.check_password(password):
            user.delete()
            messages.success(request,
                'Your account has been deleted.')
            return redirect('register')
        else:
            messages.error(request,
                'Incorrect password. Account not deleted.')
            return redirect('member_dashboard')

    return redirect('member_dashboard')
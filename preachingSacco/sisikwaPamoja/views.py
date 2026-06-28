import re
from .counties import KENYA_COUNTIES
import json
from .mpesa import stk_push
from .models import MpesaPayment
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from .models import (
    CustomUser, MemberProfile, Contribution,
    Spouse, Dependant, SerialNumberTracker
)
from .sms_service import sms_account_created, sms_dependant_added


# ══════════════════════════════════════════════
# HELPER: Build Admin Dashboard Data
# ══════════════════════════════════════════════
def _build_admin_dashboard_data():
    recent_members_queryset = (
        MemberProfile.objects.select_related('user')
        .order_by('-date_registered')[:5]
    )

    recent_members = []
    for member in recent_members_queryset:
        registered_at = timezone.localtime(member.date_registered)
        recent_members.append({
            'id': member.id,
            'full_name': member.user.get_full_name() or member.user.username,
            'county': member.county,
            'membership_type': member.get_membership_type_display(),
            'membership_key': member.membership_type,
            'paid': member.has_paid,
            'paid_label': 'Paid' if member.has_paid else 'Unpaid',
            'registered_at': registered_at.strftime('%d %b %Y'),
            'detail_url': reverse(
                f'admin:{member._meta.app_label}_{member._meta.model_name}_change',
                args=[member.pk],
            ),
        })

    total_contributions = (
        Contribution.objects.aggregate(total=Sum('amount'))['total'] or 0
    )

    return {
        'total_members': MemberProfile.objects.count(),
        'sacco_members': MemberProfile.objects.filter(
            membership_type='sacco').count(),
        'last_expense_members': MemberProfile.objects.filter(
            membership_type='last_expense').count(),
        'paid_members': MemberProfile.objects.filter(
            has_paid=True).count(),
        'unpaid_members': MemberProfile.objects.filter(
            has_paid=False).count(),
        'total_contributions': total_contributions,
        'total_spouses': Spouse.objects.count(),
        'total_dependants': Dependant.objects.count(),
        'recent_members': recent_members,
    }


# ══════════════════════════════════════════════
# HELPER: Dashboard Redirect by Role
# ══════════════════════════════════════════════
def _dashboard_redirect(user):
    if getattr(user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')
    return redirect('member_dashboard')


# ══════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════
def home_view(request):
    return render(request, 'sisikwaPamoja/home.html')


# ══════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════
def register_view(request):
    if request.method == 'POST':
        membership_type = request.POST.get('membership_type', 'sacco')
        first_name = request.POST.get('first_name')
        middle_name = request.POST.get('middle_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')
        national_id = request.POST.get('national_id')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        county_of_birth = (
            request.POST.get('county') or
            request.POST.get('county_of_birth')
        )
        sub_county_of_birth = (
            request.POST.get('sub_county') or
            request.POST.get('sub_county_of_birth')
        )
        physical_address = request.POST.get('physical_address')
        marital_status = request.POST.get('marital_status')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        passport_photo = request.FILES.get('passport_photo')
        id_copy = request.FILES.get('id_copy')

        # Validations
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

        if MemberProfile.objects.filter(
                national_id=national_id).exists():
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

            member_profile = MemberProfile.objects.create(
                user=user,
                membership_type=membership_type,
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
                registration_fee=5000 if membership_type == 'sacco' else 0,
            )

            # Send SMS after account creation
            sms_account_created(member_profile)

            # Last Expense: save spouse and dependants
            if membership_type == 'last_expense':
                spouse_full_name = (
                    request.POST.get('spouse_full_name') or ''
                ).strip()
                spouse_dob = request.POST.get('spouse_date_of_birth')

                # NOTE: spouse, dependants, and dependant-SMS are handled inside this block


                if spouse_full_name and spouse_dob:
                    Spouse.objects.create(
                        member=member_profile,
                        full_name=spouse_full_name,
                        first_name='',
                        middle_name='',
                        last_name='',
                        gender=request.POST.get('spouse_gender') or 'female',
                        date_of_birth=spouse_dob,
                        national_id=request.POST.get(
                            'spouse_national_id') or '',
                        phone_number=request.POST.get(
                            'spouse_phone_number') or '',
                        county=request.POST.get('spouse_county') or '',
                        sub_county=request.POST.get(
                            'spouse_sub_county') or '',
                        id_copy=request.FILES.get('spouse_id_copy'),
                    )

                dep_indexes = set()
                for key in request.POST.keys():
                    if key.startswith('dep_full_name_'):
                        dep_indexes.add(key.rsplit('_', 1)[-1])

                for idx in sorted(
                    dep_indexes,
                    key=lambda x: int(x) if str(x).isdigit() else x
                ):
                    full_name = (
                        request.POST.get(f'dep_full_name_{idx}') or ''
                    ).strip()
                    relationship = request.POST.get(
                        f'dep_relationship_{idx}')
                    dep_gender = request.POST.get(f'dep_gender_{idx}')
                    dep_dob = request.POST.get(f'dep_dob_{idx}')

                    if not (full_name and relationship and
                            dep_gender and dep_dob):
                        continue

                    new_dependant = Dependant.objects.create(
                        member=member_profile,
                        full_name=full_name,
                        relationship=relationship,
                        gender=dep_gender,
                        date_of_birth=dep_dob,
                        phone_number=(request.POST.get(f'dep_phone_{idx}') or '').strip() or None,
                        email=(request.POST.get(f'dep_email_{idx}') or '').strip() or None,
                        id_or_birth_cert_number=(request.POST.get(f'dep_id_{idx}') or '').strip() or None,
                        supporting_document=request.FILES.get(f'dep_doc_{idx}'),
                    )

                    # Send SMS per dependant created
                    sms_dependant_added(member_profile, new_dependant)




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

        messages.success(request, 'Account created! You can now log in.')
        return redirect(f"{reverse('register')}?registered=1")

    return render(request,
        'sisikwaPamoja/register.html',
        {
            'counties': json.dumps(KENYA_COUNTIES),
            'public_nav': True,
        })


# ══════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════
def login_view(request):
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
        'sisikwaPamoja/login.html',
        {'public_nav': True})


# ══════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════
def logout_view(request):
    logout(request)
    return redirect('login')


# ══════════════════════════════════════════════
# FORGOT PASSWORD
# ══════════════════════════════════════════════
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


# ══════════════════════════════════════════════
# MEMBER DASHBOARD
# ══════════════════════════════════════════════
@login_required
def member_dashboard(request):
    if getattr(request.user, 'role', None) != 'member':
        return _dashboard_redirect(request.user)

    profile = MemberProfile.objects.filter(
        user=request.user
    ).select_related('user').first()

    # Get recent contributions
    contributions = []
    if profile:
        contributions = Contribution.objects.filter(
            member=profile
        ).order_by('-calculated_at')[:5]

    return render(request,
        'sisikwaPamoja/dashboard_member.html', {
            'profile': profile,
            'contributions': contributions,
        })


# ══════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════
@login_required
def admin_dashboard(request):
    if getattr(request.user, 'role', None) not in (
            'superadmin', 'staff'):
        return _dashboard_redirect(request.user)

    dashboard_data = _build_admin_dashboard_data()
    # B: recent registrations + SMSLog events
    from .models import SMSLog
    recent_sms_logs = SMSLog.objects.select_related('member', 'member__user').all()[:10]

    # keep it simple for the template
    dashboard_data['recent_sms_logs'] = [
        {
            'id': l.id,
            'member_name': getattr(l.member.user, 'get_full_name', lambda: '')() or (l.member.user.username if l.member and l.member.user else ''),
            'event_type': l.event_type,
            'status': l.status,
            'message_preview': (l.message[:80] + '...') if getattr(l, 'message', None) and len(l.message) > 80 else getattr(l, 'message', '') ,
            'created_at': timezone.localtime(l.created_at).strftime('%d %b %Y %H:%M') if l.created_at else '',
        }
        for l in recent_sms_logs
    ]

    return render(request, 'sisikwaPamoja/dashboard_admin.html', dashboard_data)



# ══════════════════════════════════════════════
# ADMIN DASHBOARD STATS (JSON API)
# ══════════════════════════════════════════════
@staff_member_required
def admin_dashboard_stats(request):
    dashboard_data = _build_admin_dashboard_data()
    return JsonResponse({
        'total_members': dashboard_data['total_members'],
        'sacco_members': dashboard_data['sacco_members'],
        'last_expense_members': dashboard_data['last_expense_members'],
        'paid_members': dashboard_data['paid_members'],
        'unpaid_members': dashboard_data['unpaid_members'],
        'total_contributions': float(
            dashboard_data['total_contributions']),
        'total_spouses': dashboard_data['total_spouses'],
        'total_dependants': dashboard_data['total_dependants'],
    })


# ══════════════════════════════════════════════
# MY PROFILE
# ══════════════════════════════════════════════
@login_required
def profile_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).select_related('user').first()

    return render(request,
        'sisikwaPamoja/profile.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# EDIT PROFILE
# ══════════════════════════════════════════════
from django.shortcuts import get_object_or_404
from django.forms import modelformset_factory
from .forms import (
    MemberProfileEditForm,
    SpouseEditForm,
    DependantForm,
)


@login_required
def profile_edit_view(request):
    """
    Allow logged-in member to edit their own profile.
    Handles: personal details, spouse, dependants.
    """

    # ── Get the member's profile ──────────────────
    profile = get_object_or_404(
        MemberProfile,
        user=request.user
    )

    # ── Dependant formset ─────────────────────────
    # Allows editing multiple dependants at once
    DependantFormSet = modelformset_factory(
        Dependant,
        form=DependantForm,
        extra=0,        # don't show empty forms
        can_delete=True # allow removing dependants
    )

    # ── Spouse form — only if married ─────────────
    spouse_instance = getattr(profile, 'spouse', None)
    is_married      = profile.marital_status == 'married'

    if request.method == 'POST':

        profile_form = MemberProfileEditForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        spouse_form = SpouseEditForm(
            request.POST,
            request.FILES,
            instance=spouse_instance,
        ) if is_married else None

        dependant_formset = DependantFormSet(
            request.POST,
            request.FILES,
            queryset=Dependant.objects.filter(member=profile),
        )

        # ── Check all forms are valid ─────────────
        profile_valid   = profile_form.is_valid()
        spouse_valid    = (
            spouse_form.is_valid()
            if spouse_form else True
        )
        dependants_valid = dependant_formset.is_valid()

        if profile_valid and spouse_valid and dependants_valid:

            # Save profile
            profile_form.save()

            # Save spouse if married
            if spouse_form:
                spouse = spouse_form.save(commit=False)
                spouse.member = profile
                spouse.save()

            # Save dependants
            instances = dependant_formset.save(commit=False)

            for dep in instances:
                dep.member = profile
                dep.save()

            # Delete removed dependants
            for dep in dependant_formset.deleted_objects:
                dep.delete()

            messages.success(
                request,
                'Your profile has been updated successfully!'
            )
            return redirect('profile_edit')

        else:
            messages.error(
                request,
                'Please fix the errors below and try again.'
            )

    else:
        # GET request — pre-fill forms with existing data
        profile_form = MemberProfileEditForm(
            instance=profile,
            user=request.user,
        )

        spouse_form = SpouseEditForm(
            instance=spouse_instance,
        ) if is_married else None

        dependant_formset = DependantFormSet(
            queryset=Dependant.objects.filter(member=profile),
        )

    return render(request, 'sisikwaPamoja/profile_edit.html', {
        'profile_form':       profile_form,
        'spouse_form':        spouse_form,
        'dependant_formset':  dependant_formset,
        'profile':            profile,
        'is_married':         is_married,
    })


# ══════════════════════════════════════════════
# CONTRIBUTIONS

# ══════════════════════════════════════════════
@login_required
def contributions_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    contributions = []
    contribution_obj = None

    if profile:
        contributions = Contribution.objects.filter(
            member=profile
        ).order_by('-calculated_at')
        contribution_obj = getattr(profile, 'contribution', None)

    return render(request,
        'sisikwaPamoja/contributions.html', {
            'profile': profile,
            'contributions': contributions,
            'contribution_obj': contribution_obj,
        })


# ══════════════════════════════════════════════
# SAVINGS (Sacco Members Only)
# ══════════════════════════════════════════════
@login_required
def savings_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    # Redirect non-sacco members
    if not profile or profile.membership_type != 'sacco':
        messages.error(request,
            'Savings are only available to Sacco members.')
        return redirect('member_dashboard')

    return render(request,
        'sisikwaPamoja/savings.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# LOANS (Sacco Members Only)
# ══════════════════════════════════════════════
@login_required
def loans_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    # Redirect non-sacco members
    if not profile or profile.membership_type != 'sacco':
        messages.error(request,
            'Loans are only available to Sacco members.')
        return redirect('member_dashboard')

    return render(request,
        'sisikwaPamoja/loans.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# LOAN APPLICATION (Sacco Members Only)
# ══════════════════════════════════════════════
@login_required
def loan_apply_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    # Redirect non-sacco members
    if not profile or profile.membership_type != 'sacco':
        messages.error(request,
            'Loans are only available to Sacco members.')
        return redirect('member_dashboard')

    # Must have paid registration fee
    if not profile.has_paid:
        messages.error(request,
            'Please complete your registration payment first.')
        return redirect('member_dashboard')

    if request.method == 'POST':
        # Loan application logic comes here
        messages.info(request,
            'Loan application submitted. '
            'We will review and contact you shortly.')
        return redirect('loans')

    return render(request,
        'sisikwaPamoja/loan_apply.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# FAMILY COVERAGE (Last Expense Only)
# ══════════════════════════════════════════════
@login_required
def family_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).select_related('user').first()

    # Redirect non last expense members
    if not profile or profile.membership_type != 'last_expense':
        messages.error(request,
            'Family coverage is only available to '
            'Last Expense members.')
        return redirect('member_dashboard')

    spouse = None
    try:
        spouse = profile.spouse
    except Exception:
        pass

    dependants = profile.dependants.all()

    return render(request,
        'sisikwaPamoja/family.html', {
            'profile': profile,
            'spouse': spouse,
            'dependants': dependants,
        })


# ══════════════════════════════════════════════
# ADD DEPENDANT (Last Expense Only)
# ══════════════════════════════════════════════
@login_required
def add_dependant_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    # Redirect non last expense members
    if not profile or profile.membership_type != 'last_expense':
        messages.error(request,
            'This feature is only available to '
            'Last Expense members.')
        return redirect('member_dashboard')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        relationship = request.POST.get('relationship')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        document = request.FILES.get('supporting_document')

        if not all([full_name, relationship, gender, date_of_birth]):
            messages.error(request,
                'Please fill in all required fields.')
            return redirect('add_dependant')

        Dependant.objects.create(
            member=profile,
            full_name=full_name,
            relationship=relationship,
            gender=gender,
            date_of_birth=date_of_birth,
            phone_number=phone_number or None,
            email=email or None,
            id_or_birth_cert_number=id_number or None,
            supporting_document=document,
        )

        messages.success(request,
            f'{full_name} has been added as a dependant.')
        return redirect('family')

    return render(request,
        'sisikwaPamoja/add_dependant.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# STATEMENTS
# ══════════════════════════════════════════════
@login_required
def statements_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    contributions = []
    if profile:
        contributions = Contribution.objects.filter(
            member=profile
        ).order_by('-calculated_at')

    return render(request,
        'sisikwaPamoja/statements.html', {
            'profile': profile,
            'contributions': contributions,
        })


# ══════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════
@login_required
def notifications_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    return render(request,
        'sisikwaPamoja/notifications.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════
@login_required
def settings_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        # Change password
        if action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')

            if not request.user.check_password(old_password):
                messages.error(request,
                    'Current password is incorrect.')
            elif new_password1 != new_password2:
                messages.error(request,
                    'New passwords do not match.')
            elif len(new_password1) < 8:
                messages.error(request,
                    'Password must be at least 8 characters.')
            else:
                request.user.set_password(new_password1)
                request.user.save()
                messages.success(request,
                    'Password changed successfully. '
                    'Please log in again.')
                return redirect('login')

        # Update basic profile (first/middle/last name)
        if action == 'update_profile':
            first_name = request.POST.get('first_name', '').strip()
            middle_name = request.POST.get('middle_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()

            user = request.user
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save()

            if profile:
                profile.middle_name = middle_name
                profile.save()

            messages.success(request, 'Profile updated successfully.')

        # fallthrough redirects back to settings

        return redirect('settings')

    return render(request,
        'sisikwaPamoja/settings.html', {
            'profile': profile,
        })


# ══════════════════════════════════════════════
# DELETE ACCOUNT
# ══════════════════════════════════════════════
@login_required
def delete_account(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user

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


@login_required
def mpesa_payment_view(request):
    """
    Page where member initiates STK Push
    """
    profile = MemberProfile.objects.filter(
        user=request.user
    ).first()

    if request.method == 'POST':
        phone_number = request.POST.get('phone')
        amount       = request.POST.get('amount')
        description  = request.POST.get('description',
            'SisiPamoja Payment')

        phone_number = (phone_number or '').strip()
        phone_check = re.sub(r'\D', '', phone_number)

        if not (len(phone_check) == 10 and
                phone_check.startswith(('07', '01'))):
            messages.error(
                request,
                'Invalid phone number. Use format 0712345678.'
            )
            return redirect('mpesa_payment')

        # Send STK Push
        result = stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=profile.national_id,
            description=description
        )

        if result['success']:
            # Save pending payment
            MpesaPayment.objects.create(
                member=profile,
                phone_number=phone_number,
                amount=amount,
                account_reference=profile.national_id,
                description=description,
                checkout_request_id=result.get('checkout_id'),
                merchant_request_id=result.get('merchant_id'),
                status='pending'
            )
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])

        return redirect('mpesa_payment')

    # Get payment history
    payments = MpesaPayment.objects.filter(
        member=profile
    ).order_by('-created_at')[:10] if profile else []

    # Determine amount to pay
    if profile:
        if profile.has_paid:
            # Monthly contribution
            contribution = getattr(profile, 'contribution', None)
            default_amount = contribution.amount if contribution else 0
            payment_type = 'Monthly Contribution'
        else:
            # Registration fee
            default_amount = profile.registration_fee or 0
            payment_type = 'Registration Fee'
    else:
        default_amount = 0
        payment_type = 'Payment'

    return render(request,
        'sisikwaPamoja/mpesa_payment.html', {
            'profile': profile,
            'payments': payments,
            'default_amount': default_amount,
            'payment_type': payment_type,
            'phone': profile.phone_number if profile else '',
        })


@csrf_exempt
def mpesa_callback(request):
    """
    Safaricom sends payment result here
    This must be a public URL (no login required)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            callback = data.get('Body', {}).get(
                'stkCallback', {})

            checkout_id = callback.get('CheckoutRequestID')
            result_code = callback.get('ResultCode')
            result_desc = callback.get('ResultDesc')

            # Find the payment
            payment = MpesaPayment.objects.filter(
                checkout_request_id=checkout_id
            ).first()

            if payment:
                if result_code == 0:
                    # Payment successful
                    items = callback.get(
                        'CallbackMetadata', {}
                    ).get('Item', [])

                    receipt = ''
                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            receipt = item.get('Value', '')

                    payment.status = 'success'
                    payment.mpesa_receipt = receipt
                    payment.result_description = result_desc
                    payment.save()

                    # Mark member as paid
                    member = payment.member
                    member.has_paid = True
                    member.save()

                else:
                    # Payment failed or cancelled
                    payment.status = 'failed'
                    payment.result_description = result_desc
                    payment.save()

        except Exception as e:
            print(f"Callback error: {e}")

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
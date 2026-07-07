import re
from .counties import KENYA_COUNTIES
import json
from .mpesa import stk_push
from .models import MpesaPayment
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.forms import modelformset_factory
from django.utils import timezone
from .forms import (
    LoanApplicationForm, LoanGuarantorFormSet,
    MemberProfileEditForm, SpouseEditForm, DependantForm,
)
from .models import (
    CustomUser, MemberProfile, Contribution,
    Spouse, Dependant, SerialNumberTracker,
    LoanApplication,MpesaPayment,MemberPayment
)
from .sms_service import sms_account_created, sms_dependant_added, sms_loan_applied


def assign_serial_number(member_profile):
    """
    Assigns a serial number to a member
    after their payment is confirmed.
    Only assigns once — never overwrites.
    """
    # Already has a serial number — do nothing
    if member_profile.serial_number:
        return member_profile.serial_number

    # Get or create the tracker for this membership type
    tracker, created = SerialNumberTracker.objects.get_or_create(
        membership_type=member_profile.membership_type
    )

    # Generate the next serial number
    serial = tracker.get_next_serial()

    # Save it to the member profile
    member_profile.serial_number = serial
    member_profile.save()

    return serial

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
                registration_fee=200 if membership_type == 'sacco' else 0,
            )
            #Auto-calculate annual fee right after creation
            member_profile.annual_fee = member_profile.calculate_annual_fee()
            member_profile.save()

            # Send SMS after account creation
            sms_account_created(member_profile)

            # Last Expense: save spouse and dependants
            if membership_type == 'last_expense':
                spouse_full_name = (
                    request.POST.get('spouse_full_name') or ''
                ).strip()
                spouse_dob = request.POST.get('spouse_date_of_birth')

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
    payments = []
    fee_breakdown = None

    
    if profile:
        #Read from members payment contribution
        payments= MemberPayment.objects.filter(
            member=profile
        ).order_by('-payment_date')[:5]
        fee_breakdown = profile.get_fee_breakdown()

    return render(request,
        'sisikwaPamoja/dashboard_member.html', {
            'profile': profile,
            'contributions': payments,
            'fee_breakdown': fee_breakdown,
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

    from .models import SMSLog
    recent_sms_logs = SMSLog.objects.select_related(
        'member', 'member__user').all()[:10]

    dashboard_data['recent_sms_logs'] = [
        {
            'id': l.id,
            'member_name': getattr(l.member.user, 'get_full_name', lambda: '')() or (
                l.member.user.username if l.member and l.member.user else ''),
            'event_type': l.event_type,
            'status': l.status,
            'message_preview': (l.message[:80] + '...') if getattr(l, 'message', None) and len(l.message) > 80 else getattr(l, 'message', ''),
            'created_at': timezone.localtime(l.created_at).strftime('%d %b %Y %H:%M') if l.created_at else '',
        }
        for l in recent_sms_logs
    ]

    return render(request,
        'sisikwaPamoja/dashboard_admin.html', dashboard_data)


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
@login_required
def profile_edit_view(request):
    profile = get_object_or_404(MemberProfile, user=request.user)

    DependantFormSet = modelformset_factory(
        Dependant,
        form=DependantForm,
        extra=0,
        can_delete=True
    )

    spouse_instance = getattr(profile, 'spouse', None)
    is_married = profile.marital_status == 'married'

    if request.method == 'POST':
        profile_form = MemberProfileEditForm(
            request.POST, request.FILES,
            instance=profile, user=request.user,
        )
        spouse_form = SpouseEditForm(
            request.POST, request.FILES,
            instance=spouse_instance,
        ) if is_married else None

        dependant_formset = DependantFormSet(
            request.POST, request.FILES,
            queryset=Dependant.objects.filter(member=profile),
        )

        profile_valid = profile_form.is_valid()
        spouse_valid = spouse_form.is_valid() if spouse_form else True
        dependants_valid = dependant_formset.is_valid()

        if profile_valid and spouse_valid and dependants_valid:
            profile_form.save()

            if spouse_form:
                spouse = spouse_form.save(commit=False)
                spouse.member = profile
                spouse.save()

            instances = dependant_formset.save(commit=False)
            for dep in instances:
                dep.member = profile
                dep.save()

            for dep in dependant_formset.deleted_objects:
                dep.delete()

            messages.success(request,
                'Your profile has been updated successfully!')
            return redirect('profile_edit')
        else:
            messages.error(request,
                'Please fix the errors below and try again.')

    else:
        profile_form = MemberProfileEditForm(
            instance=profile, user=request.user)
        spouse_form = SpouseEditForm(
            instance=spouse_instance) if is_married else None
        dependant_formset = DependantFormSet(
            queryset=Dependant.objects.filter(member=profile))

    return render(request, 'sisikwaPamoja/profile_edit.html', {
        'profile_form': profile_form,
        'spouse_form': spouse_form,
        'dependant_formset': dependant_formset,
        'profile': profile,
        'is_married': is_married,
    })


# ══════════════════════════════════════════════
# CONTRIBUTIONS
# ══════════════════════════════════════════════
@login_required
def contributions_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user).first()

    contributions = []
    contribution_obj = None

    if profile:
        contributions = Contribution.objects.filter(
            member=profile).order_by('-calculated_at')
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
    # ── Guard: admins never hit member pages
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

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
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    if not profile or profile.membership_type != 'sacco':
        messages.error(request,
            'Loans are only available to Sacco members.')
        return redirect('member_dashboard')

    # ── Fetch this member's loan applications
    loans = LoanApplication.objects.filter(
        member=profile
    ).order_by('-applied_at')

    active_loans = loans.filter(
        status__in=['approved', 'disbursed'])

    return render(request,
        'sisikwaPamoja/loans.html', {
            'profile': profile,
            'loans': loans,
            'active_loans': active_loans,
            'active_loans_count': active_loans.count(),
            'total_borrowed': sum(
                l.amount_applied for l in active_loans),
        })

# ══════════════════════════════════════════════
# LOAN APPLICATION (Sacco Members Only)
# ══════════════════════════════════════════════
@login_required
def loan_apply_view(request):
    # ── Guard 1: admins and staff never hit this view
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    # ── Guard 2: sacco members only
    if not profile or profile.membership_type != 'sacco':
        messages.error(request,
            'Loans are only available to Sacco members.')
        return redirect('member_dashboard')

    # ── Guard 3: must have paid registration fee
    if not profile.has_paid:
        messages.error(request,
            'Please complete your registration payment first.')
        return redirect('member_dashboard')

    if request.method == 'POST':
        form = LoanApplicationForm(request.POST, request.FILES)

        if form.is_valid():
            loan = form.save(commit=False)
            loan.member = profile
            loan.save()

            formset = LoanGuarantorFormSet(
                request.POST, request.FILES, instance=loan)

            if formset.is_valid():
                formset.save()

                # Notify member via SMS
                sms_loan_applied(profile, loan.amount_applied)

                messages.success(request,
                    'Loan application submitted. '
                    'We will review and contact you shortly.')
                return redirect('loan_status', pk=loan.pk)
            else:
                # Roll back loan if guarantors are invalid
                loan.delete()
                messages.error(request,
                    'Please fix the errors in the '
                    'guarantor details below.')
        else:
            formset = LoanGuarantorFormSet(
                request.POST, request.FILES)
            messages.error(request,
                'Please fix the errors below and try again.')
    else:
        form = LoanApplicationForm(initial={
            'employer_business_name': getattr(
                profile, 'employer_business_name', ''),
            'occupation': getattr(
                profile, 'occupation', ''),
        })
        formset = LoanGuarantorFormSet()

    return render(request,
        'sisikwaPamoja/loan_apply.html', {
            'profile': profile,
            'form': form,
            'formset': formset,
        })


# ══════════════════════════════════════════════
# LOAN STATUS (Single Application)
# ══════════════════════════════════════════════
@login_required
def loan_status_view(request, pk):
    # ── Guard: admins never hit member pages
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    loan = LoanApplication.objects.filter(
        pk=pk, member=profile).first()

    if not loan:
        messages.error(request, 'Loan application not found.')
        return redirect('loans')

    return render(request,
        'sisikwaPamoja/loan_status.html', {
            'profile': profile,
            'loan': loan,
        })


# ══════════════════════════════════════════════
# MY LOANS (List)
# ══════════════════════════════════════════════
@login_required
def my_loans_view(request):
    # ── Guard: admins never hit member pages
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    loans = LoanApplication.objects.filter(
        member=profile
    ).order_by('-applied_at') if profile else []

    return render(request,
        'sisikwaPamoja/my_loans.html', {
            'profile': profile,
            'loans': loans,
        })


# ══════════════════════════════════════════════
# FAMILY COVERAGE (Last Expense Only)
# ══════════════════════════════════════════════
@login_required
def family_view(request):
    # ── Guard: admins never hit member pages
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user
    ).select_related('user').first()

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
    # ── Guard: admins never hit member pages
    if getattr(request.user, 'role', None) in ('superadmin', 'staff'):
        return redirect('admin_dashboard')

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    if not profile or profile.membership_type != 'last_expense':
        messages.error(request,
            'This feature is only available to '
            'Last Expense members.')
        return redirect('member_dashboard')

    form = DependantForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        dependant = form.save(commit=False)
        dependant.member = profile
        dependant.save()

        messages.success(request,
            f'{dependant.full_name} has been added as a dependant.')
        return redirect('family')

    return render(request,
        'sisikwaPamoja/add_dependant.html', {
            'profile': profile,
            'form': form,
        })


# ══════════════════════════════════════════════
# STATEMENTS
# ══════════════════════════════════════════════
@login_required
def statements_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user).first()

    contributions = []
    if profile:
        contributions = Contribution.objects.filter(
            member=profile).order_by('-calculated_at')

    return render(request,
        'sisikwaPamoja/statements.html', {
            'profile': profile,
            'contributions': contributions,
        })

# ══════════════════════════════════════════════
# STATEMENT PDF DOWNLOAD
# ══════════════════════════════════════════════
@login_required
def statement_pdf_view(request):
    from xhtml2pdf import pisa
    from django.http import HttpResponse
    import io
    from .models import MemberPayment

    profile = MemberProfile.objects.filter(
        user=request.user).first()

    if not profile:
        return redirect('member_dashboard')

    # M-Pesa payments
    mpesa_payments = MpesaPayment.objects.filter(
        member=profile,
        status='success'
    ).order_by('-created_at')

    # Admin recorded payments
    member_payments = MemberPayment.objects.filter(
        member=profile
    ).order_by('-payment_date')

    # Loans
    loans = LoanApplication.objects.filter(
        member=profile
    ).order_by('-applied_at')

    active_loans = loans.filter(
        status__in=['approved', 'disbursed'])

    # Calculate real total paid
    mpesa_total = sum(p.amount for p in mpesa_payments)
    member_total = sum(p.amount for p in member_payments)
    real_total = mpesa_total + member_total

    context = {
        'profile':            profile,
        'mpesa_payments':     mpesa_payments,
        'member_payments':    member_payments,
        'loans':              loans,
        'active_loans_count': active_loans.count(),
        'generated_at':       timezone.now(),
        'real_total':         real_total,
        'payment_count':      mpesa_payments.count() + member_payments.count(),
    }

    html_string = render_to_string(
        'sisikwaPamoja/statement_pdf.html', context)

    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(html_string, dest=pdf_buffer)
    pdf_file = pdf_buffer.getvalue()

    member_name = profile.user.get_full_name().replace(' ', '_')
    filename    = f"SisiPamoja_Statement_{member_name}.pdf"

    response = HttpResponse(
        pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{filename}"')
    return response

# ══════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════
@login_required
def notifications_view(request):
    from .models import SMSLog
    profile = MemberProfile.objects.filter(
        user=request.user).first()

    sms_logs = []
    if profile:
        sms_logs = SMSLog.objects.filter(
            member=profile
        ).order_by('-created_at')[:50]

    # Map event types to display config
    event_config = {
        'account_created':       {'title': 'Account Created',          'icon': 'fa-user-check',      'color': '#15803D', 'bg': '#F0FDF4', 'border': '#15803D'},
        'member_approved':       {'title': 'Membership Approved',       'icon': 'fa-check-circle',    'color': '#15803D', 'bg': '#F0FDF4', 'border': '#15803D'},
        'mpesa_success':         {'title': 'Payment Received',          'icon': 'fa-money-bill-wave', 'color': '#15803D', 'bg': '#F0FDF4', 'border': '#15803D'},
        'contribution_received': {'title': 'Contribution Received',     'icon': 'fa-coins',           'color': '#15803D', 'bg': '#F0FDF4', 'border': '#15803D'},
        'loan_applied':          {'title': 'Loan Application Received', 'icon': 'fa-file-alt',        'color': '#1565C0', 'bg': '#EFF6FF', 'border': '#1565C0'},
        'loan_approved':         {'title': 'Loan Approved',             'icon': 'fa-thumbs-up',       'color': '#15803D', 'bg': '#F0FDF4', 'border': '#15803D'},
        'loan_rejected':         {'title': 'Loan Not Approved',         'icon': 'fa-times-circle',    'color': '#DC2626', 'bg': '#FEF2F2', 'border': '#DC2626'},
        'loan_disbursed':        {'title': 'Loan Disbursed',            'icon': 'fa-hand-holding-usd','color': '#1565C0', 'bg': '#EFF6FF', 'border': '#1565C0'},
        'dependant_added':       {'title': 'Dependant Added',           'icon': 'fa-users',           'color': '#92400E', 'bg': '#FFF7ED', 'border': '#EA580C'},
        'password_reset':        {'title': 'Password Reset',            'icon': 'fa-lock',            'color': '#475569', 'bg': '#F8FAFC', 'border': '#94A3B8'},
    }

    notifications = []
    for log in sms_logs:
        config = event_config.get(log.event_type, {
            'title': log.get_event_type_display(),
            'icon': 'fa-bell',
            'color': '#475569',
            'bg': '#F8FAFC',
            'border': '#94A3B8',
        })
        notifications.append({
            'title':      config['title'],
            'icon':       config['icon'],
            'color':      config['color'],
            'bg':         config['bg'],
            'border':     config['border'],
            'message':    log.message,
            'created_at': log.created_at,
            'status':     log.status,
        })

    return render(request,
        'sisikwaPamoja/notifications.html', {
            'profile':       profile,
            'notifications': notifications,
            'total':         len(notifications),
        })


# ══════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════
@login_required
def settings_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user).first()

    if request.method == 'POST':
        action = request.POST.get('action')

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


# ══════════════════════════════════════════════
# MPESA PAYMENT
# ══════════════════════════════════════════════
@login_required
def mpesa_payment_view(request):
    profile = MemberProfile.objects.filter(
        user=request.user).first()

    if request.method == 'POST':
        phone_number = request.POST.get('phone')
        amount = request.POST.get('amount')
        description = request.POST.get('description',
            'SisiPamoja Payment')

        phone_number = (phone_number or '').strip()
        phone_check = re.sub(r'\D', '', phone_number)

        if not (len(phone_check) == 10 and
                phone_check.startswith(('07', '01'))):
            messages.error(request,
                'Invalid phone number. Use format 0712345678.')
            return redirect('mpesa_payment')

        result = stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=profile.national_id,
            description=description
        )

        if result['success']:
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

    payments = MpesaPayment.objects.filter(
        member=profile
    ).order_by('-created_at')[:10] if profile else []

    if profile:
        if not profile.registration_fee_paid:
            default_amount = 200
            payment_type = 'Registration Fee'
            description = 'One-time registration fee for new members.'
        elif not profile.annual_fee_paid:
            annual = profile.calculate_annual_fee()
            default_amount = annual
            if profile.membership_type == 'sacco':
                payment_type = 'Capital Share'
                description = 'Capital share payment for Sacco members.'
            else:
                payment_type = 'Annual Welfare Contribution'
                description = 'Annual welfare contribution'

        else:
            annual = profile.calculate_annual_fee()
            default_amount = annual
            if profile.membership_type == 'sacco':
                payment_type = 'Capital Share'
                description = 'Capital share payment for Sacco members.'
            else:
                payment_type = 'Annual Contribution'
                description = 'Annual welfare contribution'

    else:
        default_amount = 0
        payment_type = 'Payment'
        description =''
            

    return render(request,
        'sisikwaPamoja/mpesa_payment.html', {
            'profile': profile,
            'payments': payments,
            'default_amount': default_amount,
            'payment_type': payment_type,
            'phone': profile.phone_number if profile else '',
        })


#MPESA CALLBACK
@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            callback = data.get('Body', {}).get(
                'stkCallback', {})

            checkout_id = callback.get('CheckoutRequestID')
            result_code = callback.get('ResultCode')
            result_desc = callback.get('ResultDesc')

            payment = MpesaPayment.objects.filter(
                checkout_request_id=checkout_id
            ).first()

            if payment:
                if result_code == 0:
                    # Get receipt
                    items = callback.get(
                        'CallbackMetadata', {}
                    ).get('Item', [])

                    receipt = ''
                    for item in items:
                        if item.get('Name') == 'MpesaReceiptNumber':
                            receipt = item.get('Value', '')

                    # Update payment
                    payment.status = 'success'
                    payment.mpesa_receipt = receipt
                    payment.result_description = result_desc
                    payment.save()

                    member = payment.member

                    # ── Determine payment type
                    if not member.registration_fee_paid:
                        # First payment = registration fee
                        payment_type = 'registration'
                        description = 'Registration Fee - One time payment'
                        member.registration_fee_paid = True

                    elif not member.annual_fee_paid:
                        # Second payment
                        if member.membership_type == 'sacco':
                            #Sacco members pay capital share
                            payment_type = 'capital_share'
                            description = 'Capital Share '
                        else:   
                            #Last Expense members pay annual fee
                            payment_type = 'annual'
                            description = 'Annual Welfare Contribution'

                        
                        member.annual_fee_paid = True
                        member.has_paid = True

                    else:
                        # Subsequent payments
                        if member.membership_type == 'sacco':
                            payment_type = 'capital_share'
                            description = 'Capital Share '
                        else:
                            payment_type = 'contibution'
                            description = 'Welfare Contribution'
                        

                    # ── Record this payment
                    MemberPayment.objects.create(
                        member=member,
                        payment_type=payment_type,
                        amount=payment.amount,
                        mpesa_receipt=receipt,
                        description=description,
                        notes=f"M-Pesa payment - {receipt}"
                    )

                    # ── Update total paid
                    member.total_paid = (
                        member.total_paid + payment.amount
                    )

                    # ── Auto-calculate and save annual fee
                    member.annual_fee = member.calculate_annual_fee()
                    member.save()

                    # ── Generate serial number
                    # We need a serial number as soon as the member is marked paid
                    # (either via callback or via admin action).
                    # Ensure it happens exactly once.
                    if member.has_paid and not member.serial_number:
                        assign_serial_number(member)


                    # ── Send SMS
                    try:
                        from .sms_service import (
                            sms_mpesa_success,
                            sms_member_approved
                        )
                        sms_mpesa_success(
                            member, payment.amount, receipt)

                        if payment_type == 'registration':
                            sms_member_approved(member)

                    except Exception as sms_error:
                        print(f"SMS error: {sms_error}")

                else:
                    payment.status = 'failed'
                    payment.result_description = result_desc
                    payment.save()

        except Exception as e:
            print(f"Callback error: {e}")

    return JsonResponse({
        'ResultCode': 0,
        'ResultDesc': 'Success'
    })
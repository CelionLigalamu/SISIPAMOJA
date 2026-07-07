from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from datetime import date
from django.utils.html import format_html
from django.urls import reverse
from .models import LoanApplication, LoanGuarantor
from .models import (
    CustomUser,
    MemberProfile,
    Spouse,
    Dependant,
    Contribution,
    SerialNumberTracker,
    SMSLog,
    MemberPayment,
)


# ══════════════════════════════════════
# CUSTOM USER
# ══════════════════════════════════════
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        'get_full_name',
        'email',
        'super_admin',
    ]
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

    @admin.display(boolean=True, description='Super Admin')
    def super_admin(self, obj):
        return obj.is_superuser

    def get_full_name(self, obj):
        full_name = obj.get_full_name().strip()
        if full_name:
            return full_name
        return obj.username
    get_full_name.short_description = 'Name'


admin.site.register(CustomUser, CustomUserAdmin)


# ══════════════════════════════════════
# MEMBER PROFILE FORMS
# ══════════════════════════════════════
class DateOfBirthWidget(forms.MultiWidget):
    def __init__(self, attrs=None, onchange=None, year_start=1900):
        select_attrs = dict(attrs or {})
        if onchange:
            select_attrs['onchange'] = onchange

        widgets = [
            forms.Select(
                attrs=select_attrs,
                choices=[('', 'Day')] + [
                    (str(day), str(day)) for day in range(1, 32)
                ]
            ),
            forms.Select(
                attrs=select_attrs,
                choices=[('', 'Month')] + [
                    ('1', 'Jan'), ('2', 'Feb'), ('3', 'Mar'),
                    ('4', 'Apr'), ('5', 'May'), ('6', 'Jun'),
                    ('7', 'Jul'), ('8', 'Aug'), ('9', 'Sep'),
                    ('10', 'Oct'), ('11', 'Nov'), ('12', 'Dec'),
                ]
            ),
            forms.Select(
                attrs=select_attrs,
                choices=[('', 'Year')] + [
                    (str(year), str(year))
                    for year in range(date.today().year, year_start - 1, -1)
                ]
            ),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.day, value.month, value.year]
        return [None, None, None]

    def value_from_datadict(self, data, files, name):
        day   = data.get(f'{name}_0')
        month = data.get(f'{name}_1')
        year  = data.get(f'{name}_2')
        if day and month and year:
            return [day, month, year]
        return None


class DateOfBirthField(forms.MultiValueField):
    widget = DateOfBirthWidget

    def __init__(self, *args, onchange=None, year_start=1900, **kwargs):
        fields = (
            forms.IntegerField(min_value=1,          max_value=31),
            forms.IntegerField(min_value=1,          max_value=12),
            forms.IntegerField(min_value=year_start, max_value=date.today().year),
        )
        kwargs['widget'] = DateOfBirthWidget(
            onchange=onchange, year_start=year_start)
        kwargs.setdefault('require_all_fields', True)
        super().__init__(fields=fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            day, month, year = data_list
            return date(year, month, day)
        return None


class MemberProfileAdminForm(forms.ModelForm):
    first_name  = forms.CharField(label='First Name')
    middle_name = forms.CharField(label='Middle Name', required=False)
    last_name   = forms.CharField(label='Last Name')
    email       = forms.EmailField(label='Email', required=True)
    age_display = forms.CharField(
        label='Age', required=False, disabled=True, initial='-- years')
    date_of_birth = DateOfBirthField(
        label='Date of Birth', onchange='updateMemberAge()')

    class Media:
        js = ('sisikwaPamoja/js/admin_member_age.js',)

    class Meta:
        model  = MemberProfile
        fields = [
            'membership_type',
            'registration_fee',
            'first_name',
            'email',
            'middle_name',
            'last_name',
            'gender',
            'national_id',
            'phone_number',
            'county',
            'sub_county',
            'physical_address',
            'marital_status',
            'age_display',
            'passport_photo',
            'id_copy',
            'has_paid',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            user = self.instance.user
            self.fields['first_name'].initial  = user.first_name
            self.fields['middle_name'].initial = self.instance.middle_name
            self.fields['last_name'].initial   = user.last_name
            self.fields['email'].initial       = user.email

    def save(self, commit=True):
        instance    = super().save(commit=False)
        first_name  = (self.cleaned_data.get('first_name')  or '').strip()
        middle_name = (self.cleaned_data.get('middle_name') or '').strip()
        last_name   = (self.cleaned_data.get('last_name')   or '').strip()
        email       = (self.cleaned_data.get('email')       or '').strip()

        if instance.user_id:
            user = instance.user
        else:
            user = CustomUser(role='member')

        user.username   = instance.national_id
        user.first_name = first_name
        user.last_name  = last_name
        if email:
            user.email = email

        if not user.pk:
            user.set_unusable_password()

        user.save()
        instance.user        = user
        instance.middle_name = middle_name

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class SpouseAdminForm(forms.ModelForm):
    date_of_birth = DateOfBirthField(label='Date of Birth')

    class Meta:
        model  = Spouse
        fields = [
            'member', 'full_name', 'gender', 'date_of_birth',
            'national_id', 'phone_number', 'county', 'sub_county',
            'id_copy',
        ]


class SpouseInlineForm(forms.ModelForm):
    full_name = forms.CharField(required=False)

    class Meta:
        model  = Spouse
        fields = [
            'full_name', 'first_name', 'middle_name', 'last_name',
            'gender', 'date_of_birth', 'national_id', 'phone_number',
            'county', 'sub_county', 'id_copy',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if not self.instance.full_name:
                parts = [
                    self.instance.first_name,
                    self.instance.middle_name,
                    self.instance.last_name,
                ]
                self.fields['full_name'].initial = ' '.join(
                    [p for p in parts if p])
        self.fields['id_copy'].required = False

    def clean(self):
        cleaned_data = super().clean()
        full_name = (cleaned_data.get('full_name') or '').strip()
        if not full_name:
            parts = [
                cleaned_data.get('first_name'),
                cleaned_data.get('middle_name'),
                cleaned_data.get('last_name'),
            ]
            full_name = ' '.join(
                [p.strip() for p in parts if p])
        cleaned_data['full_name'] = full_name
        return cleaned_data


class DependantAdminForm(forms.ModelForm):
    date_of_birth = DateOfBirthField(label='Date of Birth')

    class Meta:
        model  = Dependant
        fields = [
            'member', 'full_name', 'relationship', 'gender',
            'date_of_birth', 'phone_number', 'email',
            'id_or_birth_cert_number', 'supporting_document',
        ]


class SpouseInline(admin.StackedInline):
    model = Spouse
    form  = SpouseInlineForm
    extra = 0


class DependantInline(admin.TabularInline):
    model = Dependant
    extra = 0


# ══════════════════════════════════════
# ADMIN ACTION: Approve Selected Members
# ══════════════════════════════════════
@admin.action(description='✅ Approve selected members')
def approve_members(modeladmin, request, queryset):
    from .views import assign_serial_number
    from .sms_service import sms_member_approved

    approved_count = 0
    skipped_count  = 0

    for member in queryset:
        if member.has_paid:
            skipped_count += 1
            continue

        try:
            member.has_paid = True
            member.save()
            assign_serial_number(member)
            try:
                sms_member_approved(member)
            except Exception as sms_error:
                print(f"SMS error for {member}: {sms_error}")
            approved_count += 1

        except Exception as e:
            modeladmin.message_user(
                request,
                f"⚠️ Error approving "
                f"{member.user.get_full_name()}: {e}",
                level='error',
            )

    parts = []
    if approved_count:
        parts.append(
            f"✅ {approved_count} member(s) approved and "
            f"serial numbers assigned."
        )
    if skipped_count:
        parts.append(
            f"ℹ️ {skipped_count} member(s) skipped "
            f"(already approved)."
        )
    if parts:
        modeladmin.message_user(request, ' '.join(parts))


# ══════════════════════════════════════
# MEMBER PROFILE ADMIN
# ══════════════════════════════════════
@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    form    = MemberProfileAdminForm
    actions = [approve_members]

    list_display = [
        'get_passport_photo',
        'get_full_name',
        'national_id',
        'membership_type',
        'gender',
        'get_age',
        'phone_number',
        'get_county',
        'get_sub_county',
        'get_email',
        'marital_status',
        'serial_number',
        'has_paid',
        'date_registered',
    ]

    list_filter = [
        'membership_type',
        'gender',
        'marital_status',
        'has_paid',
        'date_registered',
    ]

    search_fields = [
        'user__first_name',
        'user__last_name',
        'national_id',
        'serial_number',
    ]

    readonly_fields = [
        'date_registered',
        'serial_number',
    ]

    inlines = [SpouseInline, DependantInline]

    fieldsets = (
        ('Membership', {
            'fields': (
                'membership_type',
                'serial_number',
                'has_paid',
                'registration_fee',
            )
        }),
        ('Personal Information', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
                'email',
                'gender',
                'date_of_birth',
                'age_display',
                'national_id',
                'phone_number',
                'physical_address',
                'marital_status',
            )
        }),
        ('Location', {
            'fields': (
                'county',
                'sub_county',
            )
        }),
        ('Documents', {
            'fields': (
                'passport_photo',
                'id_copy',
            )
        }),
        ('Registration Info', {
            'fields': (
                'date_registered',
            )
        }),
    )

    # ── save_model: fires serial number + SMS on manual approval
    def save_model(self, request, obj, form, change):
        if 'has_paid' in form.changed_data and obj.has_paid:
            # Save first so the object exists in DB
            super().save_model(request, obj, form, change)

            # Assign serial number only if not already assigned
            from .views import assign_serial_number
            assign_serial_number(obj)

            # Notify member via SMS
            try:
                from .sms_service import sms_member_approved
                sms_member_approved(obj)
            except Exception as e:
                print(f"SMS error: {e}")

            self.message_user(
                request,
                f"✅ {obj.user.get_full_name()} approved. "
                f"Serial number: {obj.serial_number}"
            )
        else:
            super().save_model(request, obj, form, change)

    # ── Display methods
    def get_passport_photo(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:50%; object-fit:cover;"/>',
                obj.passport_photo.url
            )
        return format_html('<span style="color:gray;">No Photo</span>')
    get_passport_photo.short_description = 'Photo'

    def get_passport_preview(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" width="200" '
                'style="border-radius:10px;"/>',
                obj.passport_photo.url
            )
        return 'No passport photo uploaded'
    get_passport_preview.short_description = 'Passport Preview'

    def get_id_copy_preview(self, obj):
        if obj.id_copy:
            if obj.id_copy.name.endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank">📄 View PDF</a>',
                    obj.id_copy.url
                )
            return format_html(
                '<img src="{}" width="300" '
                'style="border-radius:10px;"/>',
                obj.id_copy.url
            )
        return 'No ID copy uploaded'
    get_id_copy_preview.short_description = 'ID Copy Preview'

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'

    def get_age(self, obj):
        return f"{obj.get_age()} years"
    get_age.short_description = 'Age'

    def get_county(self, obj):
        return obj.county
    get_county.short_description = 'County of Birth'

    def get_sub_county(self, obj):
        return obj.sub_county
    get_sub_county.short_description = 'Sub County of Birth'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'


# ══════════════════════════════════════
# MEMBER PAYMENT ADMIN
# ══════════════════════════════════════
@admin.register(MemberPayment)
class MemberPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'get_member_name',
        'payment_type',
        'amount',
        'mpesa_receipt',
        'payment_date',
    ]
    list_filter   = ['payment_type', 'payment_date']
    search_fields = [
        'member__user__first_name',
        'member__user__last_name',
        'mpesa_receipt',
    ]
    readonly_fields = ['payment_date']

    def get_member_name(self, obj):
        return obj.member.user.get_full_name()
    get_member_name.short_description = 'Member'


# ══════════════════════════════════════
# SPOUSE ADMIN
# ══════════════════════════════════════
@admin.register(Spouse)
class SpouseAdmin(admin.ModelAdmin):
    form = SpouseAdminForm

    list_display = [
        'get_full_name',
        'gender',
        'get_age',
        'national_id',
        'phone_number',
        'get_id_photo',
        'get_member',
    ]

    search_fields = [
        'full_name', 'first_name', 'last_name',
        'national_id', 'phone_number',
    ]

    list_filter = ['gender', 'member']

    readonly_fields = ['get_member_summary']

    fieldsets = (
        ('Member', {
            'fields': ('get_member_summary', 'member')
        }),
        ('Spouse Details', {
            'fields': (
                'full_name', 'gender', 'date_of_birth',
                'national_id', 'phone_number',
                'county', 'sub_county', 'id_copy',
            )
        }),
    )

    def get_age(self, obj):
        return f"{obj.get_age()} years"
    get_age.short_description = 'Age'

    def get_full_name(self, obj):
        if obj.full_name:
            return obj.full_name
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return ' '.join([p for p in parts if p]) or '-'
    get_full_name.short_description = 'Full Name'

    def get_id_photo(self, obj):
        if obj.id_copy:
            if obj.id_copy.name.lower().endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank">📄 PDF</a>',
                    obj.id_copy.url
                )
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:6px; object-fit:cover;"/>',
                obj.id_copy.url
            )
        return '-'
    get_id_photo.short_description = 'ID Photo'

    def get_member(self, obj):
        member_name = obj.member.user.get_full_name()
        member_url  = reverse(
            f'admin:{obj.member._meta.app_label}'
            f'_{obj.member._meta.model_name}_change',
            args=[obj.member.pk],
        )
        return format_html(
            '<a href="{}">{}</a>', member_url, member_name)
    get_member.short_description = 'Belongs To'

    def get_member_summary(self, obj):
        if not obj.pk:
            return 'Save this spouse first to view the linked member.'
        return format_html(
            '<strong>{}</strong><br>'
            '<span style="color:#6b7280;">National ID: {}</span>',
            obj.member.user.get_full_name(),
            obj.member.national_id,
        )
    get_member_summary.short_description = 'Linked Member'


# ══════════════════════════════════════
# DEPENDANT ADMIN
# ══════════════════════════════════════
@admin.register(Dependant)
class DependantAdmin(admin.ModelAdmin):
    form = DependantAdminForm

    list_display = [
        'full_name', 'relationship', 'gender',
        'get_age', 'get_is_minor', 'get_birth_cert_number',
        'get_birth_cert_photo', 'phone_number', 'email',
        'get_member', 'date_added',
    ]

    search_fields = [
        'full_name', 'phone_number',
        'email', 'id_or_birth_cert_number',
    ]

    list_filter = [
        'relationship', 'gender', 'member', 'date_added',
    ]

    readonly_fields = ['get_member_summary']

    fieldsets = (
        ('Member', {
            'fields': ('get_member_summary', 'member')
        }),
        ('Dependant Details', {
            'fields': (
                'full_name', 'relationship', 'gender',
                'date_of_birth', 'phone_number', 'email',
                'id_or_birth_cert_number', 'supporting_document',
            )
        }),
    )

    def get_age(self, obj):
        return f"{obj.get_age()} years"
    get_age.short_description = 'Age'

    def get_is_minor(self, obj):
        return 'Under 18' if obj.is_minor() else 'Adult'
    get_is_minor.short_description = 'Status'

    def get_birth_cert_number(self, obj):
        return obj.id_or_birth_cert_number or '-'
    get_birth_cert_number.short_description = 'Birth Cert Number'

    def get_birth_cert_photo(self, obj):
        if obj.supporting_document:
            if obj.supporting_document.name.lower().endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank">📄 PDF</a>',
                    obj.supporting_document.url
                )
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:6px; object-fit:cover;"/>',
                obj.supporting_document.url
            )
        return '-'
    get_birth_cert_photo.short_description = 'Birth Cert Photo'

    def get_member(self, obj):
        member_name = obj.member.user.get_full_name()
        member_url  = reverse(
            f'admin:{obj.member._meta.app_label}'
            f'_{obj.member._meta.model_name}_change',
            args=[obj.member.pk],
        )
        return format_html(
            '<a href="{}">{}</a>', member_url, member_name)
    get_member.short_description = 'Belongs To'

    def get_member_summary(self, obj):
        if not obj.pk:
            return 'Save this dependant first to view the linked member.'
        return format_html(
            '<strong>{}</strong><br>'
            '<span style="color:#6b7280;">National ID: {}</span>',
            obj.member.user.get_full_name(),
            obj.member.national_id,
        )
    get_member_summary.short_description = 'Linked Member'


# ══════════════════════════════════════
# CONTRIBUTION ADMIN
# ══════════════════════════════════════
@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):

    list_display = ['get_member', 'amount', 'reason', 'calculated_at']

    search_fields = [
        'member__user__first_name',
        'member__user__last_name',
    ]

    def get_member(self, obj):
        return obj.member.user.get_full_name()
    get_member.short_description = 'Member'


# ══════════════════════════════════════
# SERIAL NUMBER TRACKER ADMIN
# ══════════════════════════════════════
@admin.register(SerialNumberTracker)
class SerialNumberTrackerAdmin(admin.ModelAdmin):

    list_display = ['membership_type', 'last_number', 'get_last_serial']

    def get_last_serial(self, obj):
        if obj.membership_type == 'sacco':
            return f"PLC-{str(obj.last_number).zfill(3)}"
        return f"PLCM-{str(obj.last_number).zfill(3)}"
    get_last_serial.short_description = 'Last Serial Generated'


# ══════════════════════════════════════
# SMS LOG ADMIN
# ══════════════════════════════════════
@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display  = [
        'phone_number', 'event_type', 'status',
        'created_at', 'sent_at',
    ]
    list_filter   = ['status', 'event_type', 'created_at']
    search_fields = ['phone_number', 'message']
    readonly_fields = [
        'member', 'phone_number', 'message', 'event_type',
        'at_message_id', 'at_cost', 'error_message',
        'retry_count', 'created_at', 'sent_at',
    ]


# ══════════════════════════════════════
# LOAN APPLICATION ADMIN
# ══════════════════════════════════════
class LoanGuarantorInline(admin.TabularInline):
    model           = LoanGuarantor
    extra           = 0
    readonly_fields = (
        'full_name', 'membership_number', 'national_id',
        'mobile_number', 'amount_guaranteed', 'id_copy',
    )


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'member', 'loan_product', 'amount_applied',
        'status', 'applied_at', 'reviewed_by',
    )
    list_filter   = ('status', 'loan_product', 'disbursement_method')
    search_fields = (
        'member__user__first_name', 'member__user__last_name',
        'member__serial_number', 'member__national_id',
        'digital_signature',
    )
    readonly_fields = (
        'member', 'employer_business_name', 'occupation',
        'monthly_income', 'loan_product', 'loan_product_other',
        'amount_applied', 'repayment_period_months',
        'proposed_monthly_installment', 'purpose_of_loan',
        'security_offered', 'security_other', 'current_sacco_savings',
        'disbursement_method', 'bank_name', 'bank_branch',
        'bank_account_number', 'mpesa_registered_name', 'mpesa_number',
        'get_id_copy', 'get_payslip', 'get_business_permit',
        'get_supporting_doc', 'digital_signature', 'applied_at',
    )
    fields  = readonly_fields + (
        'status', 'admin_notes', 'reviewed_by', 'reviewed_at')
    inlines = [LoanGuarantorInline]

    # ── Document link methods
    def get_id_copy(self, obj):
        if obj.id_copy:
            return format_html(
                '<a href="{}" target="_blank">📄 View ID Copy</a>',
                obj.id_copy.url)
        return '-'
    get_id_copy.short_description = 'ID Copy'

    def get_payslip(self, obj):
        if obj.payslip_or_statement:
            return format_html(
                '<a href="{}" target="_blank">📄 View Payslip / Statement</a>',
                obj.payslip_or_statement.url)
        return '-'
    get_payslip.short_description = 'Payslip / Statement'

    def get_business_permit(self, obj):
        if obj.business_permit:
            return format_html(
                '<a href="{}" target="_blank">📄 View Business Permit</a>',
                obj.business_permit.url)
        return '-'
    get_business_permit.short_description = 'Business Permit'

    def get_supporting_doc(self, obj):
        if obj.supporting_document:
            return format_html(
                '<a href="{}" target="_blank">📄 View Supporting Document</a>',
                obj.supporting_document.url)
        return '-'
    get_supporting_doc.short_description = 'Supporting Document'

    # ── Save with SMS notifications
    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            from django.utils import timezone
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()

            from .sms_service import (
                sms_loan_approved,
                sms_loan_rejected,
                sms_loan_disbursed,
            )
            if obj.status == 'approved':
                sms_loan_approved(obj.member, obj.amount_applied)
            elif obj.status == 'rejected':
                sms_loan_rejected(obj.member, obj.admin_notes or '')
            elif obj.status == 'disbursed':
                sms_loan_disbursed(obj.member, obj.amount_applied)

        super().save_model(request, obj, form, change)
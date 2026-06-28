from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from datetime import date
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    CustomUser,
    MemberProfile,
    Spouse,
    Dependant,
    Contribution,
    SerialNumberTracker,
    SMSLog
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
# MEMBER PROFILE
# ══════════════════════════════════════
class DateOfBirthWidget(forms.MultiWidget):
    def __init__(self, attrs=None, onchange=None, year_start=1900):
        select_attrs = dict(attrs or {})
        if onchange:
            select_attrs['onchange'] = onchange

        widgets = [
            forms.Select(attrs=select_attrs, choices=[('', 'Day')] + [(str(day), str(day)) for day in range(1, 32)]),
            forms.Select(
                attrs=select_attrs,
                choices=[('', 'Month')] + [
                    ('1', 'Jan'), ('2', 'Feb'), ('3', 'Mar'), ('4', 'Apr'),
                    ('5', 'May'), ('6', 'Jun'), ('7', 'Jul'), ('8', 'Aug'),
                    ('9', 'Sep'), ('10', 'Oct'), ('11', 'Nov'), ('12', 'Dec'),
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
        day = data.get(f'{name}_0')
        month = data.get(f'{name}_1')
        year = data.get(f'{name}_2')
        if day and month and year:
            return [day, month, year]
        return None


class DateOfBirthField(forms.MultiValueField):
    widget = DateOfBirthWidget

    def __init__(self, *args, onchange=None, year_start=1900, **kwargs):
        fields = (
            forms.IntegerField(min_value=1, max_value=31),
            forms.IntegerField(min_value=1, max_value=12),
            forms.IntegerField(min_value=year_start, max_value=date.today().year),
        )
        kwargs['widget'] = DateOfBirthWidget(onchange=onchange, year_start=year_start)
        kwargs.setdefault('require_all_fields', True)
        super().__init__(fields=fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            day, month, year = data_list
            return date(year, month, day)
        return None


class MemberProfileAdminForm(forms.ModelForm):
    first_name = forms.CharField(label='First Name')
    middle_name = forms.CharField(label='Middle Name', required=False)
    last_name = forms.CharField(label='Last Name')
    email = forms.EmailField(label='Email', required=True)
    age_display = forms.CharField(label='Age', required=False, disabled=True, initial='-- years')

    date_of_birth = DateOfBirthField(label='Date of Birth', onchange='updateMemberAge()')

    class Media:
        js = ('sisikwaPamoja/js/admin_member_age.js',)

    class Meta:
        model = MemberProfile
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

    def save(self, commit=True):
        instance = super().save(commit=False)
        first_name = (self.cleaned_data.get('first_name') or '').strip()
        middle_name = (self.cleaned_data.get('middle_name') or '').strip()
        last_name = (self.cleaned_data.get('last_name') or '').strip()
        email = (self.cleaned_data.get('email') or '').strip()

        if instance.user_id:
            user = instance.user
        else:
            user = CustomUser(role='member')

        user.username = instance.national_id
        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email

        if not user.pk:
            user.set_unusable_password()

        user.save()
        instance.user = user
        instance.middle_name = middle_name

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class SpouseAdminForm(forms.ModelForm):
    date_of_birth = DateOfBirthField(label='Date of Birth')

    class Meta:
        model = Spouse
        fields = [
            'member',
            'full_name',
            'gender',
            'date_of_birth',
            'national_id',
            'phone_number',
            'county',
            'sub_county',
            'id_copy',
        ]


class DependantAdminForm(forms.ModelForm):
    date_of_birth = DateOfBirthField(label='Date of Birth')

    class Meta:
        model = Dependant
        fields = [
            'member',
            'full_name',
            'relationship',
            'gender',
            'date_of_birth',
            'phone_number',
            'email',
            'id_or_birth_cert_number',
            'supporting_document',
        ]


class SpouseInline(admin.StackedInline):
    model = Spouse
    extra = 0


class DependantInline(admin.TabularInline):
    model = Dependant
    extra = 0


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    form = MemberProfileAdminForm

    list_display = [
        'get_passport_photo',
        'get_full_name',
        'get_id_photo',
        'national_id',
        'membership_type',
        'gender',
        'get_age',
        'phone_number',
        'get_physical_address',
        'get_email',
        'get_county',
        'get_sub_county',
        'get_spouse_status',
        'get_dependants_count',
        'marital_status',
        'serial_number',
        'has_paid',
        'date_registered',
    ]

    inlines = [SpouseInline, DependantInline]

    search_fields = [
        'user__first_name',
        'user__last_name',
        'national_id',
        'phone_number',
        'user__email',
        'serial_number',
    ]

    list_filter = [
        'membership_type',
        'gender',
        'marital_status',
        'has_paid',
        'date_registered',
    ]

    readonly_fields = [
        'date_registered',
        'serial_number',
    ]

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
                'gender',
                'date_of_birth',
                'age_display',
                'national_id',
                'phone_number',
                'email',
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

    def get_passport_photo(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:50%; '
                'object-fit:cover;"/>',
                obj.passport_photo.url
            )
        return 'No Photo'
    get_passport_photo.short_description = 'Passport Photo'

    def get_full_name(self, obj):
        parts = [obj.user.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.user.last_name)
        return ' '.join([p for p in parts if p])
    get_full_name.short_description = 'Full Name'

    def get_middle_name(self, obj):
        return obj.middle_name or '-'
    get_middle_name.short_description = 'Middle Name'

    def get_physical_address(self, obj):
        addr = (obj.physical_address or '').strip()
        if not addr:
            return '-'
        if len(addr) > 60:
            return addr[:57] + '...'
        return addr
    get_physical_address.short_description = 'Physical Address'

    def get_id_photo(self, obj):
        if obj.id_copy:
            # If it's a PDF, show a small link/icon; otherwise show a small thumbnail
            if obj.id_copy.name.endswith('.pdf'):
                return format_html('<a href="{}" target="_blank">📄 PDF</a>', obj.id_copy.url)
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:6px; object-fit:cover;"/>',
                obj.id_copy.url
            )
        return 'No ID'
    get_id_photo.short_description = 'ID Photo'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def get_age(self, obj):
        return f"{obj.get_age()} years"
    get_age.short_description = 'Age'

    def get_county(self, obj):
        return obj.county
    get_county.short_description = 'County of Birth'

    def get_sub_county(self, obj):
        return obj.sub_county
    get_sub_county.short_description = 'Sub County of Birth'

    def get_spouse_status(self, obj):
        return 'Yes' if hasattr(obj, 'spouse') else 'No'
    get_spouse_status.short_description = 'Has Spouse'

    def get_dependants_count(self, obj):
        return obj.dependants.count()
    get_dependants_count.short_description = 'Dependants'


# ══════════════════════════════════════
# SPOUSE
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
        'full_name',
        'first_name',
        'last_name',
        'national_id',
        'phone_number',
    ]

    list_filter = [
        'gender',
        'member',
    ]

    readonly_fields = [
        'get_member_summary',
    ]

    fieldsets = (
        ('Member', {
            'fields': (
                'get_member_summary',
                'member',
            )
        }),
        ('Spouse Details', {
            'fields': (
                'full_name',
                'gender',
                'date_of_birth',
                'national_id',
                'phone_number',
                'county',
                'sub_county',
                'id_copy',
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
        return ' '.join([part for part in parts if part]) or '-'
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
        member_url = reverse(
            f'admin:{obj.member._meta.app_label}_{obj.member._meta.model_name}_change',
            args=[obj.member.pk],
        )
        return format_html('<a href="{}">{}</a>', member_url, member_name)
    get_member.short_description = 'Belongs To'

    def get_member_summary(self, obj):
        if not obj.pk:
            return 'Save this spouse first to view the linked member.'
        return format_html(
            '<strong>{}</strong><br><span style="color:#6b7280;">National ID: {}</span>',
            obj.member.user.get_full_name(),
            obj.member.national_id,
        )
    get_member_summary.short_description = 'Linked Member'


# ══════════════════════════════════════
# DEPENDANT
# ══════════════════════════════════════
@admin.register(Dependant)
class DependantAdmin(admin.ModelAdmin):
    form = DependantAdminForm

    list_display = [
        'full_name',
        'relationship',
        'gender',
        'get_age',
        'get_is_minor',
        'get_birth_cert_number',
        'get_birth_cert_photo',
        'phone_number',
        'email',
        'get_member',
        'date_added',
    ]

    search_fields = [
        'full_name',
        'phone_number',
        'email',
        'id_or_birth_cert_number',
    ]

    list_filter = [
        'relationship',
        'gender',
        'member',
        'date_added',
    ]

    readonly_fields = [
        'get_member_summary',
    ]

    fieldsets = (
        ('Member', {
            'fields': (
                'get_member_summary',
                'member',
            )
        }),
        ('Dependant Details', {
            'fields': (
                'full_name',
                'relationship',
                'gender',
                'date_of_birth',
                'phone_number',
                'email',
                'id_or_birth_cert_number',
                'supporting_document',
            )
        }),
    )

    def get_age(self, obj):
        return f"{obj.get_age()} years"
    get_age.short_description = 'Age'

    def get_is_minor(self, obj):
        if obj.is_minor():
            return 'Under 18'
        return 'Adult'
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
        member_url = reverse(
            f'admin:{obj.member._meta.app_label}_{obj.member._meta.model_name}_change',
            args=[obj.member.pk],
        )
        return format_html('<a href="{}">{}</a>', member_url, member_name)
    get_member.short_description = 'Belongs To'

    def get_member_summary(self, obj):
        if not obj.pk:
            return 'Save this dependant first to view the linked member.'
        return format_html(
            '<strong>{}</strong><br><span style="color:#6b7280;">National ID: {}</span>',
            obj.member.user.get_full_name(),
            obj.member.national_id,
        )
    get_member_summary.short_description = 'Linked Member'


# ══════════════════════════════════════
# CONTRIBUTION
# ══════════════════════════════════════
@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):

    list_display = [
        'get_member',
        'amount',
        'reason',
        'calculated_at',
    ]

    search_fields = [
        'member__user__first_name',
        'member__user__last_name',
    ]

    def get_member(self, obj):
        return obj.member.user.get_full_name()
    get_member.short_description = 'Member'


# ══════════════════════════════════════
# SERIAL NUMBER TRACKER
# ══════════════════════════════════════
@admin.register(SerialNumberTracker)
class SerialNumberTrackerAdmin(admin.ModelAdmin):

    list_display = [
        'membership_type',
        'last_number',
        'get_last_serial',
    ]

    def get_last_serial(self, obj):
        if obj.membership_type == 'sacco':
            return f"PLC-{str(obj.last_number).zfill(3)}"
        else:
            return f"PLCM-{str(obj.last_number).zfill(3)}"
    get_last_serial.short_description = 'Last Serial Generated'


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = [
        'phone_number', 'event_type',
        'status', 'created_at', 'sent_at'
    ]
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['phone_number', 'message']
    readonly_fields = [
        'member', 'phone_number', 'message',
        'event_type', 'at_message_id', 'at_cost',
        'error_message', 'retry_count',
        'created_at', 'sent_at'
    ]
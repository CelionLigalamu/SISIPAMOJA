from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser, MemberProfile

admin.site.site_header = 'SISIPAMOJA Administration'
admin.site.site_title = 'SISIPAMOJA Admin Portal'
admin.site.index_title = 'SISIPAMOJA Administration'


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        'username', 'email',
        'role', 'is_staff'
    ]
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):

    list_display = [
        'get_passport_photo',
        'get_full_name',
        'gender',
        'date_of_birth',
        'get_age',
        'national_id',
        'get_id_copy',
        'phone_number',
        'get_email',
        'marital_status',
        'get_county_of_birth',
        'get_sub_county_of_birth',
        'physical_address',
        'date_registered',
    ]

    search_fields = [
        'user__first_name',
        'user__last_name',
        'national_id',
        'phone_number',
        'user__email',
        'county',
    ]

    list_filter = [
        'gender',
        'marital_status',
        'county',
        'date_registered',
    ]

    readonly_fields = [
        'date_registered',
        'get_age',
        'get_passport_preview',
        'get_id_copy_preview',
    ]

    fieldsets = (
        ('Personal Information', {
            'fields': (
                'user',
                'middle_name',
                'gender',
                'date_of_birth',
                'get_age',
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
        ('Documents & Photos', {
            'fields': (
                'passport_photo',
                'get_passport_preview',
                'id_copy',
                'get_id_copy_preview',
            )
        }),
        ('Registration Info', {
            'fields': (
                'date_registered',
            )
        }),
    )

    # Thumbnail in list view
    def get_passport_photo(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" width="50" height="50" '
                'style="border-radius:50%; '
                'object-fit:cover;"/>',
                obj.passport_photo.url
            )
        return format_html(
            '<span style="color:gray;">'
            'No Photo</span>'
        )
    get_passport_photo.short_description = 'Photo'

    # Full preview in detail view
    def get_passport_preview(self, obj):
        if obj.passport_photo:
            return format_html(
                '<img src="{}" width="200" '
                'style="border-radius:10px; '
                'object-fit:cover;"/>',
                obj.passport_photo.url
            )
        return 'No passport photo uploaded'
    get_passport_preview.short_description = \
        'Passport Photo Preview'

    # ID copy preview
    def get_id_copy_preview(self, obj):
        if obj.id_copy:
            # Check if it's a PDF
            if obj.id_copy.name.endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank" '
                    'class="button">📄 View PDF</a>',
                    obj.id_copy.url
                )
            else:
                return format_html(
                    '<img src="{}" width="300" '
                    'style="border-radius:10px;"/>',
                    obj.id_copy.url
                )
        return 'No ID copy uploaded'
    get_id_copy_preview.short_description = \
        'ID Copy Preview'

    def get_full_name(self, obj):
        parts = [
            (obj.user.first_name or '').strip(),
            (obj.middle_name or '').strip(),
            (obj.user.last_name or '').strip(),
        ]
        full = ' '.join(p for p in parts if p)
        return full or obj.user.get_username()
    get_full_name.short_description = 'Full Name'

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def get_age(self, obj):
        # Return age as a string for display. Admin sorting can be added later.
        try:
            return f"{obj.get_age()} years"
        except Exception:
            return '-'
    get_age.short_description = 'Age'

    def get_id_copy(self, obj):
        if obj.id_copy:
            if obj.id_copy.name.lower().endswith('.pdf'):
                return format_html(
                    '<a href="{}" target="_blank">📄 View PDF</a>',
                    obj.id_copy.url
                )
            else:
                return format_html(
                    '<img src="{}" width="50" height="50" style="object-fit:cover;border-radius:4px;"/>',
                    obj.id_copy.url
                )
        return format_html('<span style="color:gray;">No ID</span>')
    get_id_copy.short_description = 'ID Photo'

    def get_county_of_birth(self, obj):
        return obj.county
    get_county_of_birth.short_description = 'County_Of_Birth'

    def get_sub_county_of_birth(self, obj):
        return obj.sub_county
    get_sub_county_of_birth.short_description = 'Sub_Of_Birth'
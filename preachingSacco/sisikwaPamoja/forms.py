from django import forms
from .models import MemberProfile, Spouse, Dependant


# ══════════════════════════════════════
# MEMBER PROFILE EDIT FORM
# ══════════════════════════════════════
class MemberProfileEditForm(forms.ModelForm):

    # Extra fields from CustomUser model
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'First name',
        })
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'Last name',
        })
    )

    class Meta:
        model  = MemberProfile
        fields = [
            'middle_name',
            'gender',
            'date_of_birth',
            'phone_number',
            'county',
            'sub_county',
            'physical_address',
            'marital_status',
            'passport_photo',
            'id_copy',
        ]
        widgets = {
            'middle_name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Middle name (optional)',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
            'phone_number': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'e.g. 0712345678',
            }),
            'county': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'County of birth',
            }),
            'sub_county': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Sub county of birth',
            }),
            'physical_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows':  2,
            }),
            'marital_status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'passport_photo': forms.FileInput(attrs={
                'class':  'form-control',
                'accept': '.jpg,.jpeg,.png',
            }),
            'id_copy': forms.FileInput(attrs={
                'class':  'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png',
            }),
        }

    def __init__(self, *args, **kwargs):
        # Pull the user out so we can pre-fill first/last name
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial  = self.user.last_name

        # Make file fields not required on edit
        # (member may not want to re-upload)
        self.fields['passport_photo'].required = False
        self.fields['id_copy'].required        = False

    def save(self, commit=True):
        profile = super().save(commit=False)

        # Also save first/last name back to CustomUser
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name  = self.cleaned_data['last_name']
            self.user.save()

        if commit:
            profile.save()
        return profile


# ══════════════════════════════════════
# SPOUSE EDIT FORM
# ══════════════════════════════════════
class SpouseEditForm(forms.ModelForm):

    class Meta:
        model  = Spouse
        fields = [
            'first_name',
            'middle_name',
            'last_name',
            'gender',
            'date_of_birth',
            'national_id',
            'phone_number',
            'county',
            'sub_county',
            'id_copy',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'First name',
            }),
            'middle_name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Middle name',
            }),
            'last_name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Last name',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
            'national_id': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'e.g. 12345678',
            }),
            'phone_number': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'e.g. 0712345678',
            }),
            'county': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'County of birth',
            }),
            'sub_county': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Sub county of birth',
            }),
            'id_copy': forms.FileInput(attrs={
                'class':  'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_copy'].required = False


# ══════════════════════════════════════
# DEPENDANT EDIT FORM
# ══════════════════════════════════════
class DependantForm(forms.ModelForm):

    class Meta:
        model  = Dependant
        fields = [
            'full_name',
            'relationship',
            'gender',
            'date_of_birth',
            'phone_number',
            'email',
            'id_or_birth_cert_number',
            'supporting_document',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Full name',
            }),
            'relationship': forms.Select(attrs={
                'class': 'form-select',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type':  'date',
            }),
            'phone_number': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'e.g. 0712345678',
            }),
            'email': forms.EmailInput(attrs={
                'class':       'form-control',
                'placeholder': 'email@example.com',
            }),
            'id_or_birth_cert_number': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'ID or Birth Certificate number',
            }),
            'supporting_document': forms.FileInput(attrs={
                'class':  'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone_number'].required          = False
        self.fields['email'].required                 = False
        self.fields['id_or_birth_cert_number'].required = False
        self.fields['supporting_document'].required   = False
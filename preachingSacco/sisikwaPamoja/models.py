from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('staff', 'Staff'),
        ('member', 'Member'),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='member'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def official_name(self):
        profile_middle_name = ''

        try:
            profile_middle_name = self.profile.middle_name or ''
        except ObjectDoesNotExist:
            profile_middle_name = ''

        name_parts = [
            self.first_name,
            profile_middle_name,
            self.last_name,
        ]
        full_name = ' '.join(
            part.strip() for part in name_parts if part and part.strip()
        ).strip()

        if full_name:
            return full_name

        fallback_name = self.get_full_name().strip()
        if fallback_name:
            return fallback_name

        return self.get_username()


class MemberProfile(models.Model):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    MARITAL_STATUS_CHOICES = (
        ('single', 'Single'),
        ('married', 'Married'),
    )

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    middle_name = models.CharField(
        max_length=100, blank=True, null=True)
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    national_id = models.CharField(
        max_length=20, unique=True)
    phone_number = models.CharField(max_length=15)
    county = models.CharField(max_length=100)
    sub_county = models.CharField(max_length=100)
    physical_address = models.TextField()
    marital_status = models.CharField(
        max_length=10,
        choices=MARITAL_STATUS_CHOICES
    )

    passport_photo = models.ImageField(
        upload_to='passports/',
        blank=True,
        null=True
    )
    id_copy = models.FileField(
        upload_to='id_copies/',
        blank=True,
        null=True
    )

    date_registered = models.DateTimeField(
        auto_now_add=True)

    def get_age(self):
        from datetime import date
        today = date.today()
        dob = self.date_of_birth
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.national_id}"
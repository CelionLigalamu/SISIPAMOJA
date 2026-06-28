from django.contrib.auth.models import AbstractUser
from django.db import models
import datetime


# ══════════════════════════════════════
# CUSTOM USER
# ══════════════════════════════════════
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


# ══════════════════════════════════════
# MEMBER PROFILE
# ══════════════════════════════════════
class MemberProfile(models.Model):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    MARITAL_STATUS_CHOICES = (
        ('single', 'Single'),
        ('married', 'Married'),
    )

    MEMBERSHIP_TYPE_CHOICES = (
        ('sacco', 'Sacco Member'),
        ('last_expense', 'Last Expense Member'),
    )

    # Link to user
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # Membership Type
    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPE_CHOICES,
        default='sacco'
    )

    # Registration fee
    # Sacco        → KES 5,000
    # Last Expense → contribution based
    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Personal Details
    middle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES
    )
    date_of_birth = models.DateField()
    national_id = models.CharField(
        max_length=20,
        unique=True
    )
    phone_number = models.CharField(
        max_length=15
    )
    county = models.CharField(
        max_length=100,
        verbose_name='County of Birth'
    )
    sub_county = models.CharField(
        max_length=100,
        verbose_name='Sub County of Birth'
    )
    physical_address = models.TextField()
    marital_status = models.CharField(
        max_length=10,
        choices=MARITAL_STATUS_CHOICES
    )

    # Uploads
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

    # Serial Number
    # Sacco Member        → PLC-001
    # Last Expense Member → PLCM-001
    serial_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True
    )

    # Payment Status
    has_paid = models.BooleanField(
        default=False
    )

    # Timestamps
    date_registered = models.DateTimeField(
        auto_now_add=True
    )

    def get_age(self):
        today = datetime.date.today()
        dob = self.date_of_birth
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def get_registration_fee(self):
        if self.membership_type == 'sacco':
            return 5000
        else:
            return 0

    def generate_serial_number(self):
        tracker, created = SerialNumberTracker.objects.get_or_create(
            membership_type=self.membership_type
        )
        tracker.last_number += 1
        tracker.save()

        if self.membership_type == 'sacco':
            # Format → PLC-001
            return f"PLC-{str(tracker.last_number).zfill(3)}"
        else:
            # Format → PLCM-001
            return f"PLCM-{str(tracker.last_number).zfill(3)}"

    def __str__(self):
        return (
            f"{self.user.get_full_name()} "
            f"- {self.national_id} "
            f"({self.get_membership_type_display()})"
        )


# ══════════════════════════════════════
# SPOUSE
# Applies to BOTH membership types
# ══════════════════════════════════════
class Spouse(models.Model):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    # One member has one spouse
    member = models.OneToOneField(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='spouse'
    )

    full_name = models.CharField(
        max_length=200,
        default=''
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    middle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES
    )
    date_of_birth = models.DateField()
    national_id = models.CharField(
        max_length=20
    )
    phone_number = models.CharField(
        max_length=15
    )
    county = models.CharField(
        max_length=100,
        verbose_name='County of Birth'
    )
    sub_county = models.CharField(
        max_length=100,
        verbose_name='Sub County of Birth'
    )
    id_copy = models.FileField(
        upload_to='spouse_id_copies/',
        blank=True,
        null=True
    )

    def get_age(self):
        today = datetime.date.today()
        dob = self.date_of_birth
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def save(self, *args, **kwargs):
        if not self.full_name:
            parts = [self.first_name, self.middle_name, self.last_name]
            self.full_name = ' '.join([part for part in parts if part])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} (Spouse of {self.member})"


# ══════════════════════════════════════
# DEPENDANT
# Applies to BOTH membership types
# ══════════════════════════════════════
class Dependant(models.Model):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    RELATIONSHIP_CHOICES = (
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('relative', 'Relative'),
        ('other', 'Other'),
    )

    # One member can have many dependants
    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='dependants'
    )

    full_name = models.CharField(
        max_length=200
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )
    email = models.EmailField(
        blank=True,
        null=True
    )
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES
    )
    date_of_birth = models.DateField()

    # Under 18 → Birth Certificate Number
    # Over 18  → National ID Number
    id_or_birth_cert_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    # Under 18 → Birth Certificate upload
    # Over 18  → ID copy upload
    supporting_document = models.FileField(
        upload_to='dependant_docs/',
        blank=True,
        null=True
    )

    date_added = models.DateTimeField(
        auto_now_add=True
    )

    def get_age(self):
        today = datetime.date.today()
        dob = self.date_of_birth
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def is_minor(self):
        return self.get_age() < 18

    def __str__(self):
        return (
            f"{self.full_name} "
            f"({self.get_relationship_display()} "
            f"of {self.member})"
        )


# ══════════════════════════════════════
# CONTRIBUTION ENGINE
# Applies to BOTH membership types
# ══════════════════════════════════════
class Contribution(models.Model):

    member = models.OneToOneField(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='contribution'
    )

    # Auto calculated:
    # Immediate family only → KES 2,500
    # Dependant below 70   → KES 3,000
    # Dependant 70+        → KES 3,500
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    reason = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    calculated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.member} - KES {self.amount}"


# ══════════════════════════════════════
# SERIAL NUMBER TRACKER
# Sacco Member        → PLC-001
# Last Expense Member → PLCM-001
# ══════════════════════════════════════
class SerialNumberTracker(models.Model):

    MEMBERSHIP_TYPE_CHOICES = (
        ('sacco', 'Sacco Member'),
        ('last_expense', 'Last Expense Member'),
    )

    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPE_CHOICES,
        unique=True
    )

    # Tracks the last number used
    # Sacco:        PLC-001, PLC-002...
    # Last Expense: PLCM-001, PLCM-002...
    last_number = models.IntegerField(
        default=0
    )

    def get_next_serial(self):
        self.last_number += 1
        self.save()
        if self.membership_type == 'sacco':
            return f"PLC-{str(self.last_number).zfill(3)}"
        else:
            return f"PLCM-{str(self.last_number).zfill(3)}"

    def __str__(self):
        if self.membership_type == 'sacco':
            prefix = 'PLC'
        else:
            prefix = 'PLCM'
        return (
            f"{prefix}-"
            f"{str(self.last_number).zfill(3)}"
            f" (Last Generated)"
        )
    

class MpesaPayment(models.Model):

    STATUS_CHOICES = (
        ('pending',  'Pending'),
        ('success',  'Success'),
        ('failed',   'Failed'),
        ('cancelled','Cancelled'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='mpesa_payments'
    )

    # STK Push details
    phone_number    = models.CharField(max_length=15)
    amount          = models.DecimalField(
        max_digits=10, decimal_places=2)
    account_reference = models.CharField(max_length=50)
    description     = models.CharField(max_length=100)

    # Safaricom response
    checkout_request_id = models.CharField(
        max_length=100, blank=True, null=True)
    merchant_request_id = models.CharField(
        max_length=100, blank=True, null=True)

    # Callback data
    mpesa_receipt   = models.CharField(
        max_length=50, blank=True, null=True)
    transaction_date = models.DateTimeField(
        blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    result_description = models.TextField(
        blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.member} - KES {self.amount} "
            f"- {self.status}"
        )

class SMSLog(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent',    'Sent'),
        ('failed',  'Failed'),
    )

    EVENT_CHOICES = (
        ('account_created',    'Account Created'),
        ('member_approved',    'Member Approved'),
        ('dependant_added',    'Dependant Added'),
        ('contribution_received', 'Contribution Received'),
        ('mpesa_success',      'M-Pesa Payment Success'),
        ('loan_applied',       'Loan Applied'),
        ('loan_approved',      'Loan Approved'),
        ('loan_rejected',      'Loan Rejected'),
        ('password_reset',     'Password Reset OTP'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sms_logs'
    )

    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    event_type = models.CharField(
        max_length=30, choices=EVENT_CHOICES)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='pending')

    # Africa's Talking response data
    at_message_id = models.CharField(
        max_length=100, blank=True, null=True)
    at_cost = models.CharField(
        max_length=20, blank=True, null=True)
    error_message = models.TextField(
        blank=True, null=True)

    retry_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.phone_number} - {self.event_type} - {self.status}"

    class Meta:
        ordering = ['-created_at']
from django.contrib.auth.models import AbstractUser
from django.db import models
import datetime


# ══════════════════════════════════════
# CUSTOM USER
# ══════════════════════════════════════
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('staff',      'Staff'),
        ('member',     'Member'),
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
        ('male',   'Male'),
        ('female', 'Female'),
    )

    MARITAL_STATUS_CHOICES = (
        ('single',  'Single'),
        ('married', 'Married'),
    )

    MEMBERSHIP_TYPE_CHOICES = (
        ('sacco',        'Sacco Member'),
        ('last_expense', 'Last Expense Member'),
    )

    # ── Link to user
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # ── Membership
    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPE_CHOICES,
        default='sacco'
    )

    # ── Fees
    # Registration fee → KES 200 (flat)
    # Annual fee       → calculated based on membership + dependants
    registration_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    annual_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    registration_fee_paid = models.BooleanField(default=False)
    annual_fee_paid       = models.BooleanField(default=False)
    has_paid              = models.BooleanField(default=False)

    # ── Personal Details
    middle_name = models.CharField(
        max_length=100, blank=True, null=True)
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    national_id = models.CharField(
        max_length=20, unique=True)
    kra_pin = models.CharField(
        max_length=20,
        blank=True, 
        null=True,
        verbose_name='KRA PIN'
    )
    phone_number = models.CharField(max_length=15)
    county = models.CharField(
        max_length=100, verbose_name='County of Birth')
    sub_county = models.CharField(
        max_length=100, verbose_name='Sub County of Birth')
    physical_address = models.TextField()
    marital_status = models.CharField(
        max_length=10, choices=MARITAL_STATUS_CHOICES)

    # ── Uploads
    passport_photo = models.ImageField(
        upload_to='passports/', blank=True, null=True)
    id_copy = models.FileField(
        upload_to='id_copies/', blank=True, null=True)

    # ── Serial Number
    # Sacco Member        → PLC-001
    # Last Expense Member → PLCM-001
    serial_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True)

    # ── Timestamps
    date_registered = models.DateTimeField(auto_now_add=True)

    # ── Methods
    def get_age(self):
        today = datetime.date.today()
        dob   = self.date_of_birth
        age   = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def get_registration_fee(self):
        return 200

    def calculate_annual_fee(self):
        """
        Calculates annual fee based on membership type and dependants.
        Sacco          → KES 5,000
        Last Expense:
          Nuclear only → KES 2,500
          Extended < 70→ KES 3,000
          Extended 70+ → KES 3,500
        """
        if self.membership_type == 'sacco':
            return 5000

        dependants = self.dependants.all()
        if not dependants.exists():
            return 2500

        extended_relationships = ['parent', 'relative', 'other']
        has_extended = dependants.filter(
            relationship__in=extended_relationships
        ).exists()

        if not has_extended:
            return 2500

        extended_deps = dependants.filter(
            relationship__in=extended_relationships)

        for dep in extended_deps:
            if dep.get_age() >= 70:
                return 3500

        return 3000

    def get_fee_breakdown(self):
        """Returns a fee summary dict for display on dashboard/admin."""
        annual = self.calculate_annual_fee()
        return {
            'registration_fee': 200,
            'annual_fee':       annual,
            'total_due':        200 + annual,
            'total_paid':       self.total_paid,
            'balance':          (200 + annual) - self.total_paid,
        }

    def generate_serial_number(self):
        tracker, _ = SerialNumberTracker.objects.get_or_create(
            membership_type=self.membership_type
        )
        tracker.last_number += 1
        tracker.save()

        if self.membership_type == 'sacco':
            return f"PLC-{str(tracker.last_number).zfill(3)}"
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
        ('male',   'Male'),
        ('female', 'Female'),
    )

    member = models.OneToOneField(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='spouse'
    )

    full_name   = models.CharField(max_length=200, default='')
    first_name  = models.CharField(max_length=100, blank=True, null=True)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name   = models.CharField(max_length=100, blank=True, null=True)
    gender      = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    national_id   = models.CharField(max_length=20)
    phone_number  = models.CharField(max_length=15)
    county        = models.CharField(
        max_length=100, verbose_name='County of Birth')
    sub_county    = models.CharField(
        max_length=100, verbose_name='Sub County of Birth')
    id_copy = models.FileField(
        upload_to='spouse_id_copies/', blank=True, null=True)

    def get_age(self):
        today = datetime.date.today()
        dob   = self.date_of_birth
        age   = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    def save(self, *args, **kwargs):
        if not self.full_name:
            parts = [self.first_name, self.middle_name, self.last_name]
            self.full_name = ' '.join([p for p in parts if p])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} (Spouse of {self.member})"


# ══════════════════════════════════════
# DEPENDANT
# Applies to BOTH membership types
# ══════════════════════════════════════
class Dependant(models.Model):

    GENDER_CHOICES = (
        ('male',   'Male'),
        ('female', 'Female'),
    )

    RELATIONSHIP_CHOICES = (
        ('child',    'Child'),
        ('parent',   'Parent'),
        ('relative', 'Relative'),
        ('other',    'Other'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='dependants'
    )

    full_name    = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email        = models.EmailField(blank=True, null=True)
    relationship = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES)
    gender       = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()

    # Under 18 → Birth Certificate Number | Over 18 → National ID
    id_or_birth_cert_number = models.CharField(
        max_length=50, blank=True, null=True)
    supporting_document = models.FileField(
        upload_to='dependant_docs/', blank=True, null=True)

    date_added = models.DateTimeField(auto_now_add=True)

    def get_age(self):
        today = datetime.date.today()
        dob   = self.date_of_birth
        age   = today.year - dob.year
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
        max_digits=10, decimal_places=2, default=0)
    reason = models.CharField(
        max_length=200, blank=True, null=True)
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member} - KES {self.amount}"


# ══════════════════════════════════════
# SERIAL NUMBER TRACKER
# ══════════════════════════════════════
class SerialNumberTracker(models.Model):

    MEMBERSHIP_TYPE_CHOICES = (
        ('sacco',        'Sacco Member'),
        ('last_expense', 'Last Expense Member'),
    )

    membership_type = models.CharField(
        max_length=20,
        choices=MEMBERSHIP_TYPE_CHOICES,
        unique=True
    )
    last_number = models.IntegerField(default=0)

    def get_next_serial(self):
        self.last_number += 1
        self.save()
        if self.membership_type == 'sacco':
            return f"PLC-{str(self.last_number).zfill(3)}"
        return f"PLCM-{str(self.last_number).zfill(3)}"

    def __str__(self):
        prefix = 'PLC' if self.membership_type == 'sacco' else 'PLCM'
        return f"{prefix}-{str(self.last_number).zfill(3)} (Last Generated)"


# ══════════════════════════════════════
# MPESA PAYMENT
# ══════════════════════════════════════
class MpesaPayment(models.Model):

    STATUS_CHOICES = (
        ('pending',   'Pending'),
        ('success',   'Success'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='mpesa_payments'
    )

    phone_number      = models.CharField(max_length=15)
    amount            = models.DecimalField(max_digits=10, decimal_places=2)
    account_reference = models.CharField(max_length=50)
    description       = models.CharField(max_length=100)

    checkout_request_id = models.CharField(
        max_length=100, blank=True, null=True)
    merchant_request_id = models.CharField(
        max_length=100, blank=True, null=True)

    mpesa_receipt    = models.CharField(
        max_length=50, blank=True, null=True)
    transaction_date = models.DateTimeField(blank=True, null=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')
    result_description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.member} - KES {self.amount} - {self.status}"


# ══════════════════════════════════════
# MEMBER PAYMENT
# Tracks every payment a member makes.
# ══════════════════════════════════════
class MemberPayment(models.Model):

    PAYMENT_TYPE_CHOICES = (
        ('registration', 'Registration Fee'),
        ('capital_share', 'Capital Share'),
        ('annual',       'Annual Welfare Contribution'),
        ('contribution', 'Monthly Contribution'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('mpesa', 'M-Pesa'),
        ('cash',  'Cash'),
        ('bank',  'Bank Transfer'),
        ('admin', 'Admin Approval'),
    )

   

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='payment_records'
    )

    payment_type  = models.CharField(
        max_length=20, choices=PAYMENT_TYPE_CHOICES)
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='admin'
    )
    mpesa_receipt = models.CharField(max_length=50, blank=True, null=True)
    payment_date  = models.DateTimeField(auto_now_add=True)
    notes         = models.TextField(blank=True, null=True)

    description = models.CharField(
        max_length=200, 
        blank=True,
        null=True,
        help_text="Reason for payment"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,)
    mpesa_receipt = models.CharField(
        max_length=50, blank=True, null=True)
    payment_date = models.DateTimeField(
        auto_now_add=True)
    notes = models.TextField(
        blank=True, null=True)

    def __str__(self):
        return (
            f"{self.member.user.get_full_name()} - "
            f"{self.payment_type} - KES {self.amount}"
            f"KES {self.amount}"
        )

    class Meta:
        ordering = ['-payment_date']


# ══════════════════════════════════════
# SMS LOG
# ══════════════════════════════════════
class SMSLog(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent',    'Sent'),
        ('failed',  'Failed'),
    )

    EVENT_CHOICES = (
        ('account_created',       'Account Created'),
        ('member_approved',       'Member Approved'),
        ('dependant_added',       'Dependant Added'),
        ('contribution_received', 'Contribution Received'),
        ('mpesa_success',         'M-Pesa Payment Success'),
        ('loan_applied',          'Loan Applied'),
        ('loan_approved',         'Loan Approved'),
        ('loan_rejected',         'Loan Rejected'),
        ('loan_disbursed',        'Loan Disbursed'),
        ('password_reset',        'Password Reset OTP'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sms_logs'
    )

    phone_number = models.CharField(max_length=15)
    message      = models.TextField()
    event_type   = models.CharField(max_length=30, choices=EVENT_CHOICES)
    status       = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')

    at_message_id = models.CharField(max_length=100, blank=True, null=True)
    at_cost       = models.CharField(max_length=20, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count   = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at    = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.phone_number} - {self.event_type} - {self.status}"

    class Meta:
        ordering = ['-created_at']


# ══════════════════════════════════════
# LOAN APPLICATION
# ══════════════════════════════════════
class LoanApplication(models.Model):

    LOAN_PRODUCT_CHOICES = (
        ('development',   'Development Loan'),
        ('emergency',     'Emergency Loan'),
        ('school_fees',   'School Fees Loan'),
        ('business',      'Business Loan'),
        ('asset_finance', 'Asset Finance Loan'),
        ('salary_advance','Salary Advance'),
        ('other',         'Other'),
    )

    SECURITY_CHOICES = (
        ('savings',    'Deposits/Savings'),
        ('guarantors', 'Guarantors'),
        ('logbook',    'Logbook'),
        ('title_deed', 'Title Deed'),
        ('other',      'Other'),
    )

    DISBURSEMENT_CHOICES = (
        ('bank',  'Bank Transfer'),
        ('mpesa', 'M-Pesa'),
    )

    STATUS_CHOICES = (
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed','Disbursed'),
    )

    member = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name='loan_applications'
    )

    # ── Section A
    employer_business_name = models.CharField(
        max_length=200, blank=True, null=True)
    occupation = models.CharField(
        max_length=150, blank=True, null=True)
    monthly_income = models.DecimalField(
        max_digits=12, decimal_places=2)

    # ── Section B
    loan_product = models.CharField(
        max_length=30, choices=LOAN_PRODUCT_CHOICES)
    loan_product_other = models.CharField(
        max_length=100, blank=True, null=True)
    amount_applied = models.DecimalField(
        max_digits=12, decimal_places=2)
    repayment_period_months = models.IntegerField()
    proposed_monthly_installment = models.DecimalField(
        max_digits=12, decimal_places=2)
    purpose_of_loan = models.TextField()

    # ── Section C
    security_offered = models.CharField(
        max_length=20, choices=SECURITY_CHOICES)
    security_other = models.CharField(
        max_length=100, blank=True, null=True)
    current_sacco_savings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    # ── Section E
    disbursement_method = models.CharField(
        max_length=10, choices=DISBURSEMENT_CHOICES)
    bank_name = models.CharField(
        max_length=150, blank=True, null=True)
    bank_branch = models.CharField(
        max_length=150, blank=True, null=True)
    bank_account_number = models.CharField(
        max_length=50, blank=True, null=True)
    mpesa_registered_name = models.CharField(
        max_length=150, blank=True, null=True)
    mpesa_number = models.CharField(
        max_length=15, blank=True, null=True)

    # ── Documents
    id_copy = models.FileField(
        upload_to='loan_documents/ids/', blank=True, null=True)
    payslip_or_statement = models.FileField(
        upload_to='loan_documents/payslips/', blank=True, null=True)
    business_permit = models.FileField(
        upload_to='loan_documents/permits/', blank=True, null=True)
    supporting_document = models.FileField(
        upload_to='loan_documents/supporting/', blank=True, null=True)

    # ── Declaration
    digital_signature = models.CharField(
        max_length=200,
        help_text="Typed full name as signature")

    # ── Status & Admin
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes  = models.TextField(blank=True, null=True)
    reviewed_by  = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_loans')
    reviewed_at  = models.DateTimeField(blank=True, null=True)
    applied_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.member.user.get_full_name()} - "
            f"KES {self.amount_applied} - {self.status}"
        )

    class Meta:
        ordering = ['-applied_at']


# ══════════════════════════════════════
# LOAN GUARANTOR (up to 3 per loan)
# ══════════════════════════════════════
class LoanGuarantor(models.Model):

    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='guarantors'
    )

    full_name          = models.CharField(max_length=200)
    membership_number  = models.CharField(
        max_length=50, blank=True, null=True)
    national_id        = models.CharField(max_length=20)
    mobile_number      = models.CharField(max_length=15)
    amount_guaranteed  = models.DecimalField(
        max_digits=12, decimal_places=2)
    id_copy = models.FileField(
        upload_to='loan_documents/guarantor_ids/',
        blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} - KES {self.amount_guaranteed}"


# ══════════════════════════════════════
# ANNOUNCEMENTS
# ══════════════════════════════════════
class Announcement(models.Model):

    CATEGORY_CHOICES = (
        ('general',      'General'),
        ('payment',      'Payment'),
        ('loan',         'Loan'),
        ('agm',          'AGM / Meeting'),
        ('maintenance',  'Maintenance'),
        ('alert',        'Alert'),
    )

    COLOR_CHOICES = (
        ('green',  'Green'),
        ('orange', 'Orange'),
        ('blue',   'Blue'),
        ('gold',   'Gold'),
    )

    title      = models.CharField(max_length=200)
    body       = models.TextField()
    category   = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general'
    )
    color      = models.CharField(
        max_length=10,
        choices=COLOR_CHOICES,
        default='green'
    )
    is_active  = models.BooleanField(
        default=True,
        help_text="Uncheck to hide from members"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
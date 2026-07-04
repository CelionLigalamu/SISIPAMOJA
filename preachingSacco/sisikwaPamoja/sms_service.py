import africastalking
from django.conf import settings
from .models import SMSLog


def _init_sms():
    """Initialize Africa's Talking SDK"""
    africastalking.initialize(
        settings.AT_USERNAME,
        settings.AT_API_KEY
    )
    return africastalking.SMS


def format_phone(phone_number):
    """Convert phone to 254 format required by AT"""
    phone = str(phone_number).strip().replace(' ', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
    elif not phone.startswith('254'):
        phone = '254' + phone
    return '+' + phone


def send_sms(phone_number, message, event_type, member=None, max_retries=2):
    """
    Send SMS via Africa's Talking with logging and retry.

    phone_number → e.g. 0712345678
    message      → text to send
    event_type   → one of SMSLog.EVENT_CHOICES keys
    member       → MemberProfile instance (optional)
    """
    formatted_phone = format_phone(phone_number)

    # Create log entry first (pending)
    log = SMSLog.objects.create(
        member=member,
        phone_number=formatted_phone,
        message=message,
        event_type=event_type,
        status='pending'
    )

    attempt = 0
    while attempt <= max_retries:
        try:
            sms = _init_sms()
            response = sms.send(message, [formatted_phone])

            recipients = response.get('SMSMessageData', {}).get('Recipients', [])

            if recipients:
                recipient = recipients[0]
                status_code = recipient.get('statusCode')

                if status_code == 101:  # Success code
                    log.status = 'sent'
                    log.at_message_id = recipient.get('messageId')
                    log.at_cost = recipient.get('cost')
                    log.sent_at = timezone.now()
                    log.retry_count = attempt
                    log.save()
                    return {'success': True, 'log': log}
                else:
                    log.error_message = recipient.get('status')
            else:
                log.error_message = 'No recipients in response'

        except Exception as e:
            log.error_message = str(e)

        attempt += 1
        log.retry_count = attempt
        log.save()

    # All retries failed
    log.status = 'failed'
    log.save()
    return {'success': False, 'log': log}


from django.utils import timezone


# ══════════════════════════════════════
# SMS TEMPLATES
# ══════════════════════════════════════

def sms_account_created(member):
    message = (
        f"Welcome to SisiPamoja! Your account has been "
        f"created successfully. We will notify you once "
        f"your membership is approved."
    )
    return send_sms(
        member.phone_number, message,
        'account_created', member
    )


def sms_member_approved(member):
    message = (
        f"Congratulations! Your SisiPamoja membership is "
        f"now active. Member Number: {member.serial_number}"
    )
    return send_sms(
        member.phone_number, message,
        'member_approved', member
    )


def sms_dependant_added(member, dependant):
    message = (
        f"{dependant.full_name} has been added as your "
        f"dependant at SisiPamoja Welfare Sacco."
    )
    return send_sms(
        member.phone_number, message,
        'dependant_added', member
    )


def sms_dependant_notify(dependant):
    """Notify the dependant themselves if they have a phone"""
    if not dependant.phone_number:
        return None
    message = (
        f"Hello {dependant.full_name}, you have been added "
        f"as a dependant under {dependant.member.user.get_full_name()} "
        f"at SisiPamoja Welfare Sacco."
    )
    return send_sms(
        dependant.phone_number, message,
        'dependant_added', dependant.member
    )


def sms_contribution_received(member, amount, receipt_number):
    message = (
        f"We have received KES {amount} from you. "
        f"Receipt Number: {receipt_number}. "
        f"Thank you - SisiPamoja Welfare."
    )
    return send_sms(
        member.phone_number, message,
        'contribution_received', member
    )


def sms_mpesa_success(member, amount, receipt_number):
    message = (
        f"Payment of KES {amount} received successfully. "
        f"M-Pesa Receipt: {receipt_number}. "
        f"Thank you - SisiPamoja Welfare."
    )
    return send_sms(
        member.phone_number, message,
        'mpesa_success', member
    )


def sms_loan_applied(member, amount):
    message = (
        f"Your loan application for KES {amount} has been "
        f"received and is under review."
    )
    return send_sms(
        member.phone_number, message,
        'loan_applied', member
    )


def sms_loan_approved(member, amount):
    message = (
        f"Congratulations! Your loan application for "
        f"KES {amount} has been approved."
    )
    return send_sms(
        member.phone_number, message,
        'loan_approved', member
    )


def sms_loan_rejected(member, reason=''):
    message = (
        f"Your loan application was not approved. "
        f"{reason} Please contact SisiPamoja for details."
    )
    return send_sms(
        member.phone_number, message,
        'loan_rejected', member
    )

def sms_loan_approved(member, amount):
    message = (
        f"Good news! KES {amount} has been disbursed to you. "
        f"Check your account/M-Pesa. Thank you - SisiPamoja Welfare."
    )
    return send_sms(
        member.phone_number, message,
        'loan_approved', member  # see note below
    )


def sms_password_reset_otp(phone_number, otp_code, member=None):
    message = (
        f"Your SisiPamoja password reset code is: {otp_code}. "
        f"Valid for 10 minutes. Do not share this code."
    )
    return send_sms(
        phone_number, message,
        'password_reset', member
    )
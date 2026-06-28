import requests
import base64
import re
from datetime import datetime
from django.conf import settings


def get_mpesa_token():
    """
    Get access token from Safaricom
    This token expires every hour
    """
    consumer_key    = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    if settings.MPESA_ENVIRONMENT == 'sandbox':
        url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    else:
        url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'

    # Encode credentials
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded = base64.b64encode(credentials.encode()).decode('utf-8')

    headers = {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        result = response.json()
        return result.get('access_token')
    except Exception as e:
        print(f"Token error: {e}")
        return None


def generate_password():
    """
    Generate the M-Pesa password
    Format: Base64(Shortcode + Passkey + Timestamp)
    """
    shortcode = settings.MPESA_SHORTCODE
    passkey   = settings.MPESA_PASSKEY
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    raw = f"{shortcode}{passkey}{timestamp}"
    encoded = base64.b64encode(raw.encode()).decode('utf-8')

    return encoded, timestamp


def stk_push(phone_number, amount, account_reference, description):
    """
    Send STK Push to member's phone

    phone_number      → e.g. 254712345678
    amount            → e.g. 5000  (whole number; decimals like 5000.00 are handled)
    account_reference → e.g. member's National ID
    description       → e.g. "Sacco Registration Fee"
    """
    token = get_mpesa_token()

    if not token:
        return {
            'success': False,
            'message': 'Could not connect to M-Pesa. Try again.'
        }

    password, timestamp = generate_password()

    if settings.MPESA_ENVIRONMENT == 'sandbox':
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    else:
        url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Normalize Kenyan phone numbers to Safaricom's required 254XXXXXXXXX format.
    phone = re.sub(r'\D', '', str(phone_number))
    if phone.startswith('0') and len(phone) == 10:
        phone = '254' + phone[1:]
    elif phone.startswith('254') and len(phone) == 12:
        pass

    if not (phone.startswith('254') and len(phone) == 12):
        return {
            'success': False,
            'message': 'Invalid phone number. Use format 0712345678.'
        }

    # FIX: Convert via float first to handle Decimal('5000.00') or string '5000.00'
    # Safaricom requires a whole number — no decimals allowed
    amount_int = int(float(amount))

    payload = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password':          password,
        'Timestamp':         timestamp,
        'TransactionType':   'CustomerPayBillOnline',
        'Amount':            amount_int,
        'PartyA':            phone,
        'PartyB':            settings.MPESA_SHORTCODE,
        'PhoneNumber':       phone,
        'CallBackURL':       settings.MPESA_CALLBACK_URL,
        'AccountReference':  str(account_reference),
        'TransactionDesc':   str(description),
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        result = response.json()

        if result.get('ResponseCode') == '0':
            return {
                'success': True,
                'message': 'STK Push sent! Check your phone.',
                'checkout_id': result.get('CheckoutRequestID'),
                'merchant_id': result.get('MerchantRequestID'),
            }
        else:
            return {
                'success': False,
                'message': result.get('errorMessage', 'Payment failed. Try again.'),
            }

    except Exception as e:
        print(f"STK Push error: {e}")
        return {
            'success': False,
            'message': 'Connection error. Please try again.',
        }
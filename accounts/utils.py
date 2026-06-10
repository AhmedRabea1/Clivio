import requests
from django.conf import settings


def send_sms(to: str, message: str):
    response = requests.post(
        'https://bulk.whysms.com/api/v3/sms/send',
        headers={
            'Authorization': f'Bearer {settings.WHYSMS_API_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        json={
            'recipient': to.lstrip('+'),
            'sender_id': settings.WHYSMS_SENDER_ID,
            'type': 'plain',
            'message': message,
        },
        timeout=10,
    )
    response.raise_for_status()

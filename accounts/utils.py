import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


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


def notify_master_user_created(user, clinic_id):
    """
    Register a locally-created doctor/assistant with the master backend's
    directory under the given master clinic_id (from the request payload).
    Never raises — a master outage should not block creating a doctor/
    assistant here. Instead, callers get a result dict back so the failure
    (and master's own error message, if any) can be surfaced in the API
    response rather than silently swallowed.

    Returns: {'synced': bool, 'error': str | None}
    """
    if not settings.MASTER_BASE_URL:
        return {'synced': False, 'error': 'MASTER_BASE_URL is not configured.'}
    if not clinic_id:
        return {'synced': False, 'error': 'clinic_id was not provided.'}

    try:
        response = requests.post(
            f'{settings.MASTER_BASE_URL}/api/clinics/{clinic_id}/users',
            json={'email': user.email, 'role': user.role, 'is_active': user.is_active},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        detail = None
        if e.response is not None:
            try:
                detail = e.response.json()
            except ValueError:
                detail = e.response.text
        error_message = str(detail) if detail else str(e)
        logger.error(
            'Failed to sync user %s to master (clinic_id=%s): %s',
            user.email, clinic_id, error_message,
        )
        return {'synced': False, 'error': error_message}

    return {'synced': True, 'error': None}

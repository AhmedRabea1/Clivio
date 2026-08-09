import requests
from django.conf import settings
from django.core.cache import cache


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


# ─── Master backend self-check ─────────────────────────────────────────────────
# Cached, lazily-refreshed status of this clinic as tracked by the master backend
# (active/expired + feature flags). The cache TTL below is what keeps this "every
# few minutes" rather than hitting master on every request — no separate scheduled
# task is needed since it's refreshed on whichever request happens to miss the cache.

MASTER_STATUS_CACHE_KEY   = 'master_clinic_status'
MASTER_STATUS_CACHE_TTL   = 300          # 5 minutes — how fresh the status must be
MASTER_STATUS_STALE_KEY   = 'master_clinic_status_stale'
MASTER_STATUS_STALE_TTL   = 60 * 60 * 24  # 24 hours — fallback if master is down

# Fail open on account status (a transient master outage shouldn't lock everyone
# out) but fail closed on unknown features (never seen = not confirmed enabled).
DEFAULT_MASTER_STATUS = {
    'is_active':       True,
    'expiration_date': None,
    'is_expired':      False,
    'features':        {},
}


def get_master_status(force_refresh=False):
    if not force_refresh:
        cached = cache.get(MASTER_STATUS_CACHE_KEY)
        if cached is not None:
            return cached

    if not settings.MASTER_BASE_URL or not settings.MASTER_CLINIC_ID:
        return DEFAULT_MASTER_STATUS

    try:
        response = requests.get(
            f'{settings.MASTER_BASE_URL}/api/clinics/{settings.MASTER_CLINIC_ID}/status',
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        # Master unreachable or returned garbage — fall back to the last known-good
        # status rather than immediately treating the clinic as suspended.
        return cache.get(MASTER_STATUS_STALE_KEY) or DEFAULT_MASTER_STATUS

    cache.set(MASTER_STATUS_CACHE_KEY, data, MASTER_STATUS_CACHE_TTL)
    cache.set(MASTER_STATUS_STALE_KEY, data, MASTER_STATUS_STALE_TTL)
    return data


def notify_master_user_created(user, clinic_id):
    """
    Best-effort: register a locally-created doctor/assistant with the master
    backend's directory under the given master clinic_id (chosen by whoever
    created the user, e.g. from the FE payload — not necessarily this
    deployment's own MASTER_CLINIC_ID). Never raises — a master outage should
    not block creating a doctor/assistant here.
    """
    if not settings.MASTER_BASE_URL or not clinic_id:
        return
    try:
        requests.post(
            f'{settings.MASTER_BASE_URL}/api/clinics/{clinic_id}/users',
            json={'email': user.email, 'role': user.role, 'is_active': user.is_active},
            timeout=5,
        )
    except requests.RequestException:
        pass

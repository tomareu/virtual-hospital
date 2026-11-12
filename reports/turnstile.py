import uuid

import httpx
from django.conf import settings

from .exceptions import ReportUnavailable, TurnstileFailed

SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
VERIFY_TIMEOUT = httpx.Timeout(5.0)
VERIFY_ATTEMPTS = 2


class TurnstileUnavailable(Exception):
    pass


def is_allowed_hostname(hostname, allowed_hostnames):
    return bool(hostname) and any(
        hostname == allowed or hostname.endswith(f'.{allowed}') for allowed in allowed_hostnames
    )


def _siteverify(client, payload):
    for attempt in range(1, VERIFY_ATTEMPTS + 1):
        try:
            response = client.post(SITEVERIFY_URL, data=payload)
        except httpx.TransportError:
            if attempt == VERIFY_ATTEMPTS:
                raise
            continue
        response.raise_for_status()
        return response.json()


def verify_token(token, *, secret, allowed_hostnames, transport=None):
    payload = {'secret': secret, 'response': token, 'idempotency_key': str(uuid.uuid4())}
    try:
        with httpx.Client(timeout=VERIFY_TIMEOUT, transport=transport) as client:
            result = _siteverify(client, payload)
        return result.get('success') is True and is_allowed_hostname(result.get('hostname'), allowed_hostnames)
    except (httpx.HTTPError, ValueError, AttributeError) as error:
        raise TurnstileUnavailable(type(error).__name__) from error


def require_human(token):
    if not settings.TURNSTILE_SECRET_KEY:
        raise ReportUnavailable()
    try:
        verified = verify_token(
            token,
            secret=settings.TURNSTILE_SECRET_KEY,
            allowed_hostnames=settings.TURNSTILE_ALLOWED_HOSTNAMES,
        )
    except TurnstileUnavailable as error:
        raise ReportUnavailable() from error
    if not verified:
        raise TurnstileFailed()

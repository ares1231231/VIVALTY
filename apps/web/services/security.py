"""Bot/abuse-protection helpers.

Currently implements Cloudflare Turnstile server-side verification. If no
secret is configured (dev) the verification is short-circuited as a pass so
local signup remains friction-free.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("vivalty.security")

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_enabled() -> bool:
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", "")) and bool(
        getattr(settings, "TURNSTILE_SITE_KEY", "")
    )


def verify_turnstile_token(token: str | None, remote_ip: str | None = None) -> bool:
    """Return True when the Turnstile challenge succeeded (or is disabled)."""
    if not turnstile_enabled():
        return True
    if not token:
        return False
    try:
        resp = requests.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
                **({"remoteip": remote_ip} if remote_ip else {}),
            },
            timeout=5,
        )
        data = resp.json() if resp.ok else {}
        return bool(data.get("success"))
    except Exception:
        logger.exception("Turnstile verification request failed")
        return False


def client_ip(request) -> str | None:
    """Best-effort client IP extraction behind a typical proxy chain."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

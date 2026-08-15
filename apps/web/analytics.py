"""GA4 Measurement Protocol helpers (server-side events)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _ga4_client_id(request) -> str:
    """Best-effort client id: _ga cookie when present, else stable session id."""
    raw = request.COOKIES.get("_ga", "")
    parts = raw.split(".")
    if len(parts) >= 4:
        return f"{parts[-2]}.{parts[-1]}"
    session_key = request.session.session_key
    if session_key:
        return session_key
    return str(uuid.uuid4())


def send_ga4_event(request, event_name: str, params: dict[str, Any] | None = None) -> bool:
    """
    Send an event to GA4 via Measurement Protocol.
    Returns True when the request was accepted (HTTP 2xx).
    Requires GA4_MEASUREMENT_ID + GA4_API_SECRET in env.
    """
    measurement_id = getattr(settings, "GA4_MEASUREMENT_ID", "")
    api_secret = getattr(settings, "GA4_API_SECRET", "")
    if not measurement_id or not api_secret:
        return False

    payload = {
        "client_id": _ga4_client_id(request),
        "events": [{"name": event_name, "params": params or {}}],
    }
    user_id = getattr(getattr(request, "user", None), "pk", None)
    if user_id:
        payload["user_id"] = str(user_id)

    url = (
        "https://www.google-analytics.com/mp/collect"
        f"?measurement_id={measurement_id}&api_secret={api_secret}"
    )
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("GA4 Measurement Protocol failed for event %s", event_name)
        return False


def track_sign_up_server(request, user) -> bool:
    """Record sign_up in GA4 from the server (works even when browser tracking fails)."""
    params = {"method": "email"}
    if user and getattr(user, "pk", None):
        params["engagement_time_msec"] = 1
    return send_ga4_event(request, "sign_up", params)

"""Address autocomplete via OpenStreetMap Nominatim.

Used by the listing wizard's location step to translate a free-text
address into a structured suggestion list with lat/lng. Nominatim is
free and key-less; we MUST identify ourselves via the User-Agent header
and cache aggressively to stay polite (1 req/sec/IP policy).

If the network call fails (offline dev, rate-limited, blocked egress),
the wizard silently degrades to manual lat/lng entry — no surface error.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from django.core.cache import cache

logger = logging.getLogger("vivalty.geo")

_USER_AGENT = "Vivalty/1.0 (https://vivalty.com; investor-desk@vivalty.com)"
_ENDPOINT = "https://nominatim.openstreetmap.org/search"
_CACHE_TTL = 60 * 60 * 24  # 24h — addresses don't move


def search(query: str, *, country_code: str | None = None, limit: int = 6) -> list[dict[str, Any]]:
    """Return a list of normalized suggestions for the given query.

    Each suggestion is shaped for direct rendering in the autocomplete
    dropdown::

        {"label": "12 Rue de Rivoli, 75001 Paris, France",
         "address": "12 Rue de Rivoli, 75001 Paris",
         "latitude": "48.8566",
         "longitude": "2.3522"}
    """
    q = (query or "").strip()
    if len(q) < 3:
        return []

    cache_key = f"geo:nominatim:{country_code or '-'}:{q.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
    }
    if country_code:
        params["countrycodes"] = country_code.lower()

    url = f"{_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310 (HTTPS, trusted host)
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.warning("Nominatim lookup failed for %r", q, exc_info=True)
        return []

    suggestions: list[dict[str, Any]] = []
    for item in raw:
        addr = item.get("address") or {}
        street = " ".join(
            part for part in [addr.get("house_number"), addr.get("road") or addr.get("pedestrian")] if part
        ).strip()
        locality = addr.get("city") or addr.get("town") or addr.get("village") or ""
        postcode = addr.get("postcode") or ""
        country = addr.get("country") or ""
        short = ", ".join(p for p in [street, f"{postcode} {locality}".strip(), country] if p)
        suggestions.append({
            "label": item.get("display_name") or short or q,
            "address": short or item.get("display_name") or q,
            "latitude": item.get("lat") or "",
            "longitude": item.get("lon") or "",
        })

    cache.set(cache_key, suggestions, _CACHE_TTL)
    return suggestions


__all__ = ["search"]

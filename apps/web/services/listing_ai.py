"""AI helpers for the listing wizard.

Two single-shot, non-conversational helpers:
- :func:`rewrite_description` — turns a raw owner-typed blurb into editorial,
  investor-friendly copy.
- :func:`suggest_price` — proposes an asking price from the city's avg €/m²
  and the listing area (no LLM call, deterministic math).

Both gracefully fall back to local heuristics when no `OPENAI_API_KEY` is
configured so the wizard never breaks in dev / CI.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

from apps.geo.models import City, Country

logger = logging.getLogger("vivalty.listing")


# ─── Description rewrite ────────────────────────────────────────────────────

_REWRITE_SYSTEM_PROMPT = (
    "You are Vivalty's senior copywriter for international real-estate listings. "
    "Rewrite the owner-supplied description in an editorial, investor-friendly tone. "
    "Lead with a single 12-18 word hook, then 2-3 short paragraphs covering: "
    "location & lifestyle, property highlights, investment angle (yield, demand, trend). "
    "Use concrete sensory detail, never invent facts, keep it under 180 words, "
    "no bullet points, no emojis, no markdown."
)


def rewrite_description(raw: str, *, context: dict[str, Any] | None = None) -> str:
    """Polish a draft description. Returns the rewritten text or the input
    unchanged if no LLM is available.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw

    if not settings.OPENAI_API_KEY:
        return _local_polish(raw, context or {})

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,
        )
        ctx_block = _format_context(context or {})
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Listing context:\n{ctx_block}\n\nDraft:\n{raw}"},
            ],
            temperature=0.5,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or raw
    except Exception:
        logger.exception("rewrite_description() failed; returning raw input")
        return raw


def _local_polish(raw: str, context: dict[str, Any]) -> str:
    """Deterministic offline polish — capitalises sentences, adds an investor
    closing line if the description doesn't already mention yield / ROI.
    """
    sentences = [s.strip() for s in raw.replace("\n", " ").split(".") if s.strip()]
    polished = ". ".join(s[:1].upper() + s[1:] for s in sentences)
    if polished and not polished.endswith("."):
        polished += "."

    city = context.get("city_name") or ""
    if city and city.lower() not in polished.lower():
        polished += f" Located in {city}, a market favoured by international investors."

    return polished


def _format_context(ctx: dict[str, Any]) -> str:
    lines = []
    if v := ctx.get("title"):
        lines.append(f"- Title: {v}")
    if v := ctx.get("property_type"):
        lines.append(f"- Type: {v}")
    if v := ctx.get("city_name"):
        country = ctx.get("country_name") or ""
        lines.append(f"- Location: {v}{', ' + country if country else ''}")
    if v := ctx.get("area_sqm"):
        lines.append(f"- Area: {v} m²")
    if (b := ctx.get("bedrooms")) is not None:
        lines.append(f"- Bedrooms: {b}")
    if (b := ctx.get("bathrooms")) is not None:
        lines.append(f"- Bathrooms: {b}")
    if (p := ctx.get("price")):
        cur = ctx.get("currency") or "EUR"
        lines.append(f"- Asking price: {p} {cur}")
    return "\n".join(lines) or "(no extra context)"


# ─── Price suggestion ───────────────────────────────────────────────────────

def suggest_price(
    *,
    city: City | None,
    country: Country | None,
    area_sqm: Decimal | None,
) -> dict[str, Any] | None:
    """Suggest an asking price (and a sensible band) from city benchmarks.

    Returns ``None`` when we don't have enough signal to commit to a number.
    """
    if not area_sqm or area_sqm <= 0:
        return None

    avg_per_sqm: Decimal | None = None
    source = ""
    if city and city.avg_price_sqm:
        avg_per_sqm = Decimal(city.avg_price_sqm)
        source = f"{city.name} benchmark (€/m²)"
    elif country:
        # Country-baseline fallback: rough mid-market €/m² by jurisdiction.
        # Numbers are intentionally conservative — refined per-city in admin.
        fallback = {
            "FR": 7_500, "GB": 6_800, "ES": 3_900, "CH": 12_500,
            "IT": 4_600, "AE": 4_200, "PT": 3_500,
        }.get(country.code)
        if fallback:
            avg_per_sqm = Decimal(fallback)
            source = f"{country.name} baseline (€/m²)"

    if avg_per_sqm is None:
        return None

    mid = avg_per_sqm * Decimal(area_sqm)
    low = (mid * Decimal("0.9")).quantize(Decimal("1"))
    high = (mid * Decimal("1.1")).quantize(Decimal("1"))
    return {
        "mid": int(mid),
        "low": int(low),
        "high": int(high),
        "per_sqm": int(avg_per_sqm),
        "source": source,
        "currency": (country.currency if country else "EUR"),
    }


__all__ = ["rewrite_description", "suggest_price"]

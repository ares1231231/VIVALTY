"""AI helpers for the listing wizard.

Two single-shot, non-conversational helpers:
- :func:`rewrite_description` — turns a raw owner-typed blurb into editorial,
  buyer-friendly copy.
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
    "Rewrite the owner-supplied description in an editorial, buyer-friendly tone. "
    "Lead with a single 12-18 word hook, then 2-3 short paragraphs covering: "
    "location & lifestyle, property highlights, and who the home suits best. "
    "Use concrete sensory detail, never invent facts, keep it under 180 words, "
    "no bullet points, no emojis, no markdown. Do not mention yields, ROI or "
    "investment returns."
)

_TITLE_SYSTEM_PROMPT = (
    "You write short, elegant real-estate listing titles for an international marketplace. "
    "Return ONLY one title, max 70 characters, no quotes, no emojis, no hashtags. "
    "Make it specific and attractive (location or standout feature when known). "
    "Never invent amenities that are not in the context."
)

_FULL_POLISH_SYSTEM_PROMPT = (
    "You are Vivalty's senior real-estate copywriter. Polish this listing for "
    "international buyers. Return valid JSON only, no markdown fences, with keys:\n"
    '  "title": string (max 70 chars, elegant, specific),\n'
    '  "description": string (hook + 2-3 short paragraphs, under 180 words, '
    "editorial tone, no bullets, no emojis, no markdown, never invent facts, "
    "no ROI/yield talk).\n"
    "Keep every factual detail the owner provided (beds, size, city, type)."
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

        client_kwargs: dict = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        client = OpenAI(**client_kwargs)
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
    """Deterministic offline polish — capitalises sentences, adds a closing
    line about the location if the description doesn't already mention it.
    """
    sentences = [s.strip() for s in raw.replace("\n", " ").split(".") if s.strip()]
    polished = ". ".join(s[:1].upper() + s[1:] for s in sentences)
    if polished and not polished.endswith("."):
        polished += "."

    city = context.get("city_name") or ""
    if city and city.lower() not in polished.lower():
        polished += f" Located in {city}, a destination loved by international buyers."

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


def polish_listing(draft: dict[str, Any]) -> dict[str, str]:
    """Rewrite title + description for the pre-publish preview.

    Returns ``{"title", "description"}``. Falls back to local polish when the
    LLM is unavailable. Never invents facts beyond the draft context.
    """
    raw_title = (draft.get("title") or "").strip()
    raw_desc = (draft.get("description") or "").strip()
    context = {
        "title": raw_title,
        "property_type": draft.get("property_type_display") or draft.get("property_type"),
        "city_name": draft.get("city_name"),
        "country_name": draft.get("country_name"),
        "area_sqm": draft.get("area_sqm"),
        "bedrooms": draft.get("bedrooms"),
        "bathrooms": draft.get("bathrooms"),
        "price": draft.get("price"),
        "currency": draft.get("currency"),
    }

    if not settings.OPENAI_API_KEY:
        return {
            "title": _local_title(raw_title, context),
            "description": _local_polish(raw_desc, context) if raw_desc else _local_desc_from_specs(context),
        }

    seed_desc = raw_desc or _local_desc_from_specs(context)
    try:
        from openai import OpenAI

        client_kwargs: dict = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        client = OpenAI(**client_kwargs)
        ctx_block = _format_context(context)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _FULL_POLISH_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Listing context:\n{ctx_block}\n\n"
                        f"Current title:\n{raw_title or '(none)'}\n\n"
                        f"Current description:\n{seed_desc}"
                    ),
                },
            ],
            temperature=0.55,
        )
        text = (resp.choices[0].message.content or "").strip()
        parsed = _parse_polish_json(text)
        if parsed:
            title = (parsed.get("title") or raw_title or _local_title(raw_title, context)).strip()
            desc = (parsed.get("description") or seed_desc).strip()
            return {"title": title[:90], "description": desc}
    except Exception:
        logger.exception("polish_listing() failed; using local fallback")

    return {
        "title": _local_title(raw_title, context),
        "description": _local_polish(seed_desc, context),
    }


def _parse_polish_json(text: str) -> dict[str, Any] | None:
    import json
    import re

    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return data


def _local_title(raw: str, context: dict[str, Any]) -> str:
    if raw and len(raw) >= 8:
        return raw[:1].upper() + raw[1:]
    ptype = (context.get("property_type") or "Home").replace("_", " ").title()
    city = context.get("city_name") or ""
    beds = context.get("bedrooms")
    bits = []
    if beds not in (None, "",):
        try:
            bits.append(f"{int(beds)}-bed")
        except (TypeError, ValueError):
            pass
    bits.append(ptype)
    if city:
        bits.append(f"in {city}")
    return " ".join(bits)[:70] or "Beautiful home"


def _local_desc_from_specs(context: dict[str, Any]) -> str:
    ptype = (context.get("property_type") or "property").replace("_", " ")
    city = context.get("city_name") or "a sought-after destination"
    country = context.get("country_name") or ""
    where = f"{city}, {country}".strip(", ") if country else city
    area = context.get("area_sqm")
    beds = context.get("bedrooms")
    baths = context.get("bathrooms")
    details = []
    if beds not in (None, ""):
        details.append(f"{beds} bedroom{'s' if str(beds) != '1' else ''}")
    if baths not in (None, ""):
        details.append(f"{baths} bathroom{'s' if str(baths) != '1' else ''}")
    if area:
        details.append(f"{area} m²")
    detail_line = ", ".join(details) if details else "thoughtfully proportioned living space"
    return (
        f"A distinctive {ptype} in {where}, ready for its next chapter. "
        f"With {detail_line}, it offers an inviting base for everyday living and weekends away. "
        f"Ideal for buyers seeking character, comfort and a strong sense of place."
    )


__all__ = ["rewrite_description", "suggest_price", "polish_listing"]

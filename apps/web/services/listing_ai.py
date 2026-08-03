"""AI helpers for the listing wizard.

Single-shot helpers:
- :func:`rewrite_description` / :func:`polish_listing` — vendeuse sales copy
  (property → city → opportunity).
- :func:`suggest_price` — asking price from city avg €/m² × area.

Falls back to local sales heuristics when `OPENAI_API_KEY` is missing so the
wizard never breaks in dev / CI.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any

from django.conf import settings

from apps.geo.models import City, Country

logger = logging.getLogger("vivalty.listing")


# ─── Description rewrite ────────────────────────────────────────────────────

_REWRITE_SYSTEM_PROMPT = (
    "You are an elite real-estate sales copywriter for Vivalty (international buyers). "
    "Rewrite the listing in a seductive, vendeuse, high-end marketing voice — the kind "
    "that makes someone want to book a viewing tonight.\n\n"
    "STRUCTURE (strict order, 3 short paragraphs, 140–200 words):\n"
    "1) THE PROPERTY — open with a punchy hook, then sell the home itself "
    "(light, space, lifestyle, who it suits). Use only facts from the draft/context.\n"
    "2) THE CITY — praise the city as one of the most dynamic / attractive destinations "
    "to buy in (culture, lifestyle, centrality, demand). Invent NO fake street names, "
    "NO fake amenities, NO exact % yields or ROI numbers.\n"
    "3) THE OPPORTUNITY — close with why this is a smart moment to buy "
    "(rental appeal, long-term value, scarcity) in warm sales language.\n\n"
    "Tone: cinematic, persuasive, premium. Vary wording every time — never recycle "
    "generic lines like 'a destination loved by international buyers'. "
    "No bullet points, no emojis, no markdown, no hashtags."
)

_FULL_POLISH_SYSTEM_PROMPT = (
    "You are Vivalty's star real-estate sales copywriter. Your job is to turn a thin "
    "owner draft into a irresistible listing for international buyers.\n"
    "Return valid JSON only (no markdown fences) with keys:\n"
    '  "title": max 70 chars, specific and tempting (feature + city when possible),\n'
    '  "description": 140–200 words, 3 short paragraphs in THIS order:\n'
    "    (1) Sell the PROPERTY first — hook + highlights from the facts given,\n"
    "    (2) Sell the CITY — call it one of the most dynamic/attractive places to buy, "
    "evoke lifestyle, centrality, cultural energy, buyer demand (no fake streets),\n"
    "    (3) Close on OPPORTUNITY — rental appeal / long-term value / why act now, "
    "without inventing exact yield or ROI percentages.\n"
    "Tone: vendeuse, glamorous, concrete. Never invent bedrooms, size, views or amenities "
    "not in the context. No bullets, no emojis, no markdown. Fresh phrasing every time."
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
            temperature=0.8,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text and len(text.split()) >= 40:
            return text
        return _local_polish(raw, context or {})
    except Exception:
        logger.exception("rewrite_description() failed; using local sales polish")
        return _local_polish(raw, context or {})


def _local_polish(raw: str, context: dict[str, Any]) -> str:
    """Salesy offline polish when the LLM is unavailable."""
    # Short owner blurbs get a full vendeuse rewrite from specs + their words.
    if len((raw or "").split()) < 40:
        base = _local_desc_from_specs(context)
        snippet = (raw or "").strip().rstrip(".")
        if snippet and snippet.lower() not in base.lower():
            return f"{snippet}.\n\n{base}"
        return base

    sentences = [s.strip() for s in raw.replace("\n", " ").split(".") if s.strip()]
    polished = ". ".join(s[:1].upper() + s[1:] for s in sentences)
    if polished and not polished.endswith("."):
        polished += "."
    city_pitch = _city_sales_pitch(context)
    if city_pitch and context.get("city_name", "").lower() not in polished.lower():
        polished = f"{polished}\n\n{city_pitch}"
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

    local_desc = _local_polish(raw_desc, context) if raw_desc else _local_desc_from_specs(context)
    if not settings.OPENAI_API_KEY:
        return {
            "title": _local_title(raw_title, context),
            "description": local_desc,
        }

    seed_desc = raw_desc or local_desc
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
                        f"Owner draft (may be short — expand into full sales copy):\n{seed_desc}\n\n"
                        "Write in the same language as the owner draft when obvious; "
                        "otherwise use elegant international English."
                    ),
                },
            ],
            temperature=0.8,
        )
        text = (resp.choices[0].message.content or "").strip()
        parsed = _parse_polish_json(text)
        if parsed:
            title = (parsed.get("title") or raw_title or _local_title(raw_title, context)).strip()
            desc = (parsed.get("description") or local_desc).strip()
            # Reject limp one-liners from a bad model response.
            if len(desc.split()) < 40:
                desc = local_desc
            return {"title": title[:90], "description": desc}
    except Exception:
        logger.exception("polish_listing() failed; using local fallback")

    return {
        "title": _local_title(raw_title, context),
        "description": local_desc,
    }


def _parse_polish_json(text: str) -> dict[str, Any] | None:
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


def _is_bland_title(raw: str, ptype: str, city: str) -> bool:
    """True for thin titles like « Land in Barcelona » / « beautiful house »."""
    t = (raw or "").strip().casefold()
    if not t or len(t) < 12:
        return True
    p = ptype.casefold()
    c = city.casefold()
    if t in {p, f"nice {p}", f"beautiful {p}", f"lovely {p}"}:
        return True
    if c and re.fullmatch(rf"(?:a |an |the )?{re.escape(p)}(?:s)? in {re.escape(c)}", t):
        return True
    # "{Type} in {City}" even when type label differs slightly (land vs villa).
    if c and re.fullmatch(rf"[a-z /-]{{2,40}} in {re.escape(c)}", t):
        return True
    return False


def _local_title(raw: str, context: dict[str, Any]) -> str:
    ptype = (context.get("property_type") or "Home").replace("_", " ").title()
    city = context.get("city_name") or ""
    if raw and not _is_bland_title(raw, ptype, city):
        return raw[:1].upper() + raw[1:]
    beds = context.get("bedrooms")
    area = context.get("area_sqm")
    bits = []
    if beds not in (None, ""):
        try:
            bits.append(f"{int(beds)}-bed")
        except (TypeError, ValueError):
            pass
    bits.append(ptype)
    if area:
        bits.append(f"· {area} m²")
    if city:
        bits.append(f"in {city}")
    return " ".join(bits)[:70] or "A rare opportunity awaits"


_CITY_HOOKS: dict[str, str] = {
    "barcelona": (
        "Owning in Barcelona means planting a flag in one of Europe's most magnetic "
        "cities — Mediterranean light, a walkable historic centre, and relentless "
        "international demand that keeps this market among the continent's most coveted."
    ),
    "madrid": (
        "Madrid rewards buyers who want the pulse of a true capital: culture, careers "
        "and a rental market that rarely sleeps. Few European cities combine lifestyle "
        "and long-term appeal quite like this."
    ),
    "lisbon": (
        "Lisbon has become one of Europe's most desirable places to buy — Atlantic "
        "light, a booming creative scene and year-round visitor demand that supports "
        "strong rental interest across the city."
    ),
    "porto": (
        "Porto charms with riverside character and a fast-rising international profile. "
        "Buyers come for the lifestyle and stay for a market that keeps drawing "
        "remote workers, tourists and long-term tenants."
    ),
    "paris": (
        "Paris remains the ultimate address: timeless prestige, global recognition and "
        "enduring demand from buyers and renters who refuse to compromise on location."
    ),
    "london": (
        "London offers depth few markets can match — world-class connectivity, "
        "cultural gravity and a tenant pool that keeps quality homes in constant demand."
    ),
    "dubai": (
        "Dubai is built for ambition: skyline living, tax-efficient ownership and a "
        "global community that fuels both lifestyle and rental appetite year-round."
    ),
    "milan": (
        "Milan pairs Italian design culture with serious business energy — a city "
        "where style and investment logic meet in the same postcode."
    ),
    "rome": (
        "Rome sells a lifestyle money can't invent elsewhere: history at your door, "
        "sunlit piazzas and perennial tourist demand that underpins rental appeal."
    ),
    "valencia": (
        "Valencia is the Mediterranean smart buy — sunshine, a liveable centre and "
        "growing international interest without the frenzy of the bigger capitals."
    ),
    "malaga": (
        "Málaga blends beach-city ease with a booming year-round scene — exactly "
        "the mix that attracts lifestyle buyers and short-stay demand alike."
    ),
    "marbella": (
        "Marbella is the Costa del Sol's signature address: glamour, golf and a "
        "luxury rental market that stays busy when the sun is out — which is often."
    ),
}


def _city_sales_pitch(context: dict[str, Any]) -> str:
    city = (context.get("city_name") or "").strip()
    country = (context.get("country_name") or "").strip()
    if not city:
        return (
            "This is the kind of address international buyers hunt for — a place "
            "where lifestyle and long-term rental appeal move in the same direction."
        )
    key = city.casefold()
    if key in _CITY_HOOKS:
        return _CITY_HOOKS[key]
    where = f"{city}, {country}" if country else city
    return (
        f"Imagine owning in {where} — one of the most dynamic and attractive markets "
        f"for international buyers today. A vibrant centre, lasting lifestyle pull and "
        f"steady rental interest make this the kind of city where a well-chosen property "
        f"can work as both a home and a smart long-term hold."
    )


def _local_desc_from_specs(context: dict[str, Any]) -> str:
    ptype = (context.get("property_type") or "property").replace("_", " ")
    city = context.get("city_name") or "this sought-after city"
    area = context.get("area_sqm")
    beds = context.get("bedrooms")
    baths = context.get("bathrooms")
    details = []
    if beds not in (None, ""):
        details.append(f"{beds} bedroom{'s' if str(beds) != '1' else ''}")
    if baths not in (None, ""):
        details.append(f"{baths} bathroom{'s' if str(baths) != '1' else ''}")
    if area:
        details.append(f"{area} m² of living space")
    detail_line = ", ".join(details) if details else "generous, flexible living space"

    para1 = (
        f"Step inside this {ptype} and you feel the opportunity immediately — "
        f"{detail_line}, arranged for modern living and ready to welcome its next owner. "
        f"Whether you are looking for a primary home, a pied-à-terre or a turnkey rental, "
        f"the bones of this property invite you to project your lifestyle here."
    )
    para2 = _city_sales_pitch(context)
    para3 = (
        f"Properties like this in {city} do not linger quietly. Between lifestyle demand "
        f"and the city's rental magnetism, this is the moment to secure an address that "
        f"feels as smart as it looks — before someone else does."
    )
    return f"{para1}\n\n{para2}\n\n{para3}"


__all__ = ["rewrite_description", "suggest_price", "polish_listing"]

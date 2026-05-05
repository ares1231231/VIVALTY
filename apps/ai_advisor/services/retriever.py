"""Lightweight RAG retriever over Properties / Cities / Countries.

We don't ship vector search yet (a deliberate scope choice — keeps infra
minimal), but the interface mimics one so the upgrade path is clean:

    docs = retrieve_context(user_message, session=session)
    # → list[ContextDoc] ; render with `render_context(docs)`.

Strategy:
    1. Always include any pinned property / country attached to the session.
    2. Mention the user's keywords (country names, "Lisbon", "ROI", price ranges).
    3. Pull top-N highest-scored matching properties via Postgres FTS-ish
       ILIKE + investment_score ordering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from django.db.models import Q

from apps.geo.models import City, Country
from apps.properties.models import Property


COUNTRY_ALIASES = {
    "france": "FR", "french": "FR", "paris": "FR", "lyon": "FR", "nice": "FR",
    "uk": "GB", "united kingdom": "GB", "britain": "GB", "london": "GB", "manchester": "GB",
    "spain": "ES", "spanish": "ES", "madrid": "ES", "barcelona": "ES", "valencia": "ES",
    "switzerland": "CH", "swiss": "CH", "geneva": "CH", "zurich": "CH", "lausanne": "CH",
    "italy": "IT", "italian": "IT", "milan": "IT", "rome": "IT", "florence": "IT",
    "uae": "AE", "dubai": "AE", "abu dhabi": "AE", "emirates": "AE",
    "portugal": "PT", "portuguese": "PT", "lisbon": "PT", "porto": "PT", "algarve": "PT",
}


@dataclass(frozen=True)
class ContextDoc:
    kind: str  # "property" | "country" | "city"
    id: int
    title: str
    body: str


def _detect_country_codes(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for alias, code in COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower) and code not in found:
            found.append(code)
    return found


def _detect_budget(text: str) -> tuple[int | None, int | None]:
    """Catch budgets like '100k', '€500,000', '2 million'."""
    lower = text.lower().replace(",", "")
    # 'X million' / 'X m'
    m = re.search(r"(\d+(?:\.\d+)?)\s*(million|m)\b", lower)
    if m:
        v = int(float(m.group(1)) * 1_000_000)
        return (int(v * 0.6), int(v * 1.4))
    # 'X k'
    m = re.search(r"(\d+(?:\.\d+)?)\s*k\b", lower)
    if m:
        v = int(float(m.group(1)) * 1_000)
        return (int(v * 0.6), int(v * 1.4))
    # raw number with currency
    m = re.search(r"(?:€|\$|£|usd|eur|aed)\s*(\d{4,})", lower)
    if m:
        v = int(m.group(1))
        return (int(v * 0.6), int(v * 1.4))
    return (None, None)


def _format_property(p: Property) -> ContextDoc:
    metric = getattr(p, "metric", None)
    metric_lines = "no metric computed"
    if metric:
        est = "estimated" if metric.is_estimated else "verified"
        metric_lines = (
            f"score={metric.investment_score}/100, "
            f"roi={metric.estimated_roi_min}%-{metric.estimated_roi_max}% ({est}), "
            f"yield={metric.rental_yield}%, demand={metric.demand}, "
            f"trend={metric.market_trend}, risk={metric.risk_level}"
        )
    body = (
        f"id={p.id} title={p.title!r} type={p.property_type} "
        f"city={p.city.name} country={p.country.code} "
        f"price={p.price}{p.currency} "
        f"bedrooms={p.bedrooms or '-'} area_sqm={p.area_sqm or '-'} "
        f"status={p.status} featured={p.is_featured} | {metric_lines}"
    )
    return ContextDoc(kind="property", id=p.id, title=p.title, body=body)


def _format_country(c: Country) -> ContextDoc:
    body = (
        f"code={c.code} name={c.name} currency={c.currency} "
        f"baseline_roi={c.base_roi_min}%-{c.base_roi_max}% (estimated), "
        f"baseline_yield={c.base_rental_yield}% (estimated), "
        f"demand={c.base_demand}, trend={c.base_trend}, risk={c.base_risk}. "
        f"summary={c.summary[:300]!r}"
    )
    return ContextDoc(kind="country", id=c.id, title=c.name, body=body)


def _format_city(city: City) -> ContextDoc:
    body = (
        f"id={city.id} name={city.name} country={city.country.code} "
        f"avg_price_sqm={city.avg_price_sqm or '-'} "
        f"avg_yield={city.avg_rental_yield or '-'}% "
        f"demand={city.demand or '-'} trend={city.trend or '-'} risk={city.risk or '-'} "
        f"score={city.investment_score or '-'} (city baselines may be estimated)"
    )
    return ContextDoc(kind="city", id=city.id, title=f"{city.name}, {city.country.code}", body=body)


def retrieve_context(
    user_message: str,
    *,
    pinned_property: Property | None = None,
    pinned_country: Country | None = None,
    max_properties: int = 6,
    max_countries: int = 4,
) -> list[ContextDoc]:
    docs: list[ContextDoc] = []
    seen_property_ids: set[int] = set()

    # 1) Pinned items always included
    if pinned_property is not None:
        docs.append(_format_property(pinned_property))
        seen_property_ids.add(pinned_property.id)
    if pinned_country is not None:
        docs.append(_format_country(pinned_country))

    # 2) Country detection
    country_codes = _detect_country_codes(user_message)
    if country_codes:
        for c in Country.objects.filter(code__in=country_codes):
            docs.append(_format_country(c))
            for city in c.cities.all().order_by("-investment_score")[:3]:
                docs.append(_format_city(city))
    else:
        # Generic market overview when user is exploratory
        for c in Country.objects.all()[:max_countries]:
            docs.append(_format_country(c))

    # 3) Budget filter
    price_min, price_max = _detect_budget(user_message)

    # 4) Property retrieval
    qs = (
        Property.objects.select_related("country", "city", "metric")
        .filter(status="active")
        .order_by("-metric__investment_score", "-is_featured")
    )
    if country_codes:
        qs = qs.filter(country__code__in=country_codes)
    if price_min is not None and price_max is not None:
        qs = qs.filter(price__gte=price_min, price__lte=price_max)

    # Lightweight keyword OR over title/description/city
    keywords = [w for w in re.findall(r"[A-Za-z]{4,}", user_message)][:6]
    if keywords:
        q = Q()
        for kw in keywords:
            q |= Q(title__icontains=kw) | Q(description__icontains=kw) | Q(city__name__icontains=kw)
        scored = qs.filter(q)[: max_properties * 2]
        # Fall back to default ordering if keyword search returns nothing
        chosen = list(scored) or list(qs[:max_properties])
    else:
        chosen = list(qs[:max_properties])

    for p in chosen[:max_properties]:
        if p.id in seen_property_ids:
            continue
        seen_property_ids.add(p.id)
        docs.append(_format_property(p))

    return docs


def render_context(docs: Iterable[ContextDoc]) -> str:
    """Render a compact, token-efficient context block."""
    sections = {"property": [], "country": [], "city": []}
    for d in docs:
        sections.setdefault(d.kind, []).append(f"- {d.body}")

    parts: list[str] = []
    if sections["country"]:
        parts.append("### Countries\n" + "\n".join(sections["country"]))
    if sections["city"]:
        parts.append("### Cities\n" + "\n".join(sections["city"]))
    if sections["property"]:
        parts.append("### Properties\n" + "\n".join(sections["property"]))
    return "\n\n".join(parts) or "(no platform data matched)"


def context_property_ids(docs: Iterable[ContextDoc]) -> list[int]:
    return [d.id for d in docs if d.kind == "property"]

"""Shared listing-filter logic.

Both the marketplace view and the saved-search alert command need to turn a set
of query parameters (``country``, ``type``, ``price_max`` …) into a filtered
``Property`` queryset. Keeping that in one place guarantees a saved search
returns exactly what the user saw on the marketplace when they saved it.
"""

from __future__ import annotations

from django.db.models import F, Q, QuerySet

from apps.properties.models import Property, Status


def base_active_queryset() -> QuerySet:
    return (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images", "tags")
        .filter(status=Status.ACTIVE)
    )


def apply_filters(qs: QuerySet, params) -> QuerySet:
    """Apply marketplace filters from a dict-like ``params`` (request.GET or dict)."""
    get = params.get

    if search := get("search"):
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(city__name__icontains=search)
            | Q(country__name__icontains=search)
            | Q(listing_agency__icontains=search)
            | Q(listing_ref__icontains=search)
        )
    if country := get("country"):
        qs = qs.filter(country__code__iexact=country)
    if city := get("city"):
        qs = qs.filter(city__slug=city)
    if ptype := get("type"):
        qs = qs.filter(property_type=ptype)
    if price_min := get("price_min"):
        try:
            qs = qs.filter(price__gte=float(price_min))
        except (TypeError, ValueError):
            pass
    if price_max := get("price_max"):
        try:
            qs = qs.filter(price__lte=float(price_max))
        except (TypeError, ValueError):
            pass
    if score_min := get("score_min"):
        try:
            qs = qs.filter(metric__investment_score__gte=int(score_min))
        except (TypeError, ValueError):
            pass
    if roi_min := get("roi_min"):
        try:
            qs = qs.filter(metric__estimated_roi_min__gte=float(roi_min))
        except (TypeError, ValueError):
            pass

    purpose = (get("purpose") or "buy").strip().lower()
    if purpose == "rent":
        if max_rent := get("max_rent"):
            try:
                qs = (
                    qs.filter(metric__rental_yield__gt=0)
                    .annotate(est_monthly_rent=F("price") * F("metric__rental_yield") / 1200)
                    .filter(est_monthly_rent__lte=float(max_rent))
                )
            except (TypeError, ValueError):
                pass
    elif mx := get("max_budget"):
        try:
            qs = qs.filter(price__lte=float(mx))
        except (TypeError, ValueError):
            pass

    return qs


def resolve_ordering(params) -> list[str]:
    ordering = params.get("ordering") or "-is_featured,-created_at"
    if params.get("best_match") == "1":
        ordering = "-metric__investment_score,-is_featured,-created_at"
    return [o.strip() for o in ordering.split(",") if o.strip()]


# Human-readable labels for filter params (used to name saved searches).
_TYPE_LABELS = {
    "apartment": "Apartments",
    "villa": "Villas",
    "house": "Houses",
    "commercial": "Commercial",
    "land": "Land",
    "office": "Offices",
    "retail": "Retail",
}


def describe_filters(params, *, country_names: dict[str, str] | None = None) -> str:
    """Build a short human label like 'Apartments in Portugal under €300,000'."""
    get = params.get
    bits: list[str] = []

    ptype = get("type")
    bits.append(_TYPE_LABELS.get(ptype, "Homes"))

    code = (get("country") or "").upper()
    if code:
        name = (country_names or {}).get(code, code)
        bits.append(f"in {name}")

    if city := get("city"):
        bits.append(f"· {city.replace('-', ' ').title()}")

    pmax = get("price_max") or get("max_budget")
    if pmax:
        try:
            bits.append(f"under €{int(float(pmax)):,}")
        except (TypeError, ValueError):
            pass

    if get("search"):
        bits.append(f"matching “{get('search')}”")

    return " ".join(bits) or "All homes"

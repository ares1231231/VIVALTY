"""Price comparison explorer — what a budget buys across destinations (ads-safe)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, Min, Q

from apps.geo.models import Country
from apps.properties.models import Property, Status
from apps.web.services import destinations as dest


def compare_budget(budget_eur: float) -> list[dict]:
    """Return one row per covered country showing what ``budget_eur`` can buy."""
    guides = {g.code: g for g in dest.all_guides()}
    codes = list(guides.keys())

    countries = {c.code: c for c in Country.objects.filter(code__in=codes)}

    # Listings under budget per country.
    listing_stats = {
        row["country__code"]: row
        for row in (
            Property.objects.filter(
                status=Status.ACTIVE,
                country__code__in=codes,
                price__lte=budget_eur,
            )
            .values("country__code")
            .annotate(
                count=Count("id"),
                avg_price=Avg("price"),
                min_price=Min("price"),
                avg_area=Avg("area_sqm"),
            )
        )
    }

    # Sample listing per country (cheapest featured, else cheapest).
    samples: dict[str, Property] = {}
    for code in codes:
        qs = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images")
            .filter(status=Status.ACTIVE, country__code=code, price__lte=budget_eur)
            .order_by("-is_featured", "price")
        )
        sample = qs.first()
        if sample:
            samples[code] = sample

    rows: list[dict] = []
    for code in ["PT", "ES", "FR", "IT", "GB", "AE", "CH"]:
        if code not in guides:
            continue
        g = guides[code]
        c = countries.get(code)
        stats = listing_stats.get(code, {})
        sample = samples.get(code)
        avg_sqm = float(c.cities.aggregate(a=Avg("avg_price_sqm"))["a"] or 0) if c else 0
        est_sqm = int(budget_eur / avg_sqm) if avg_sqm > 0 else None

        rows.append(
            {
                "code": code,
                "name": g.name,
                "slug": g.slug,
                "flag": c.flag_emoji if c else "📍",
                "listings_count": stats.get("count", 0),
                "avg_price": stats.get("avg_price"),
                "min_price": stats.get("min_price"),
                "avg_area": stats.get("avg_area"),
                "avg_price_sqm": avg_sqm,
                "est_sqm": est_sqm,
                "sample": sample,
                "tagline": g.tagline,
            }
        )

    return rows


def budget_presets() -> list[int]:
    return [150_000, 250_000, 300_000, 500_000, 750_000, 1_000_000]

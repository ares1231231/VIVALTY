"""Idempotently seeds a broader catalogue of cities per country.

The original `seed` management command only inserts the 3–4 cities that have
neighbourhood data attached. The hero search bar on the landing page needs a
wider city list per market so users can drill down to the destination they
actually have in mind. This data migration tops every country up with the
common investment-grade cities and stays safe to re-run (uses get_or_create).
"""

from __future__ import annotations

from django.db import migrations
from django.utils.text import slugify


EXTRA_CITIES: dict[str, list[dict[str, object]]] = {
    "FR": [
        {"name": "Marseille",     "avg_price_sqm": 3500, "avg_rental_yield": 5.4, "demand": "high",   "trend": "growth",   "risk": "medium", "score": 79, "population": 870_000},
        {"name": "Bordeaux",      "avg_price_sqm": 5200, "avg_rental_yield": 4.4, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 82, "population": 257_000},
        {"name": "Toulouse",      "avg_price_sqm": 4100, "avg_rental_yield": 5.0, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 81, "population": 498_000},
        {"name": "Cannes",        "avg_price_sqm": 7400, "avg_rental_yield": 4.0, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 77, "population": 73_000},
        {"name": "Montpellier",   "avg_price_sqm": 3900, "avg_rental_yield": 5.1, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 80, "population": 295_000},
        {"name": "Strasbourg",    "avg_price_sqm": 3700, "avg_rental_yield": 5.3, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 78, "population": 281_000},
        {"name": "Nantes",        "avg_price_sqm": 4000, "avg_rental_yield": 4.9, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 80, "population": 320_000},
        {"name": "Lille",         "avg_price_sqm": 3300, "avg_rental_yield": 5.7, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 78, "population": 233_000},
        {"name": "Saint-Tropez",  "avg_price_sqm": 12000,"avg_rental_yield": 3.2, "demand": "high",   "trend": "stable",   "risk": "medium", "score": 72, "population": 4_500},
        {"name": "Biarritz",      "avg_price_sqm": 8800, "avg_rental_yield": 3.8, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 75, "population": 25_000},
    ],
    "GB": [
        {"name": "Liverpool",     "avg_price_sqm": 2600, "avg_rental_yield": 7.2, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 84, "population": 498_000},
        {"name": "Edinburgh",     "avg_price_sqm": 4800, "avg_rental_yield": 4.9, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 81, "population": 524_000},
        {"name": "Glasgow",       "avg_price_sqm": 2700, "avg_rental_yield": 6.6, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 83, "population": 633_000},
        {"name": "Bristol",       "avg_price_sqm": 4200, "avg_rental_yield": 5.2, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 82, "population": 467_000},
        {"name": "Leeds",         "avg_price_sqm": 3000, "avg_rental_yield": 6.4, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 83, "population": 793_000},
        {"name": "Cambridge",     "avg_price_sqm": 6200, "avg_rental_yield": 4.6, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 80, "population": 145_000},
        {"name": "Oxford",        "avg_price_sqm": 6400, "avg_rental_yield": 4.5, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 80, "population": 152_000},
        {"name": "Brighton",      "avg_price_sqm": 5300, "avg_rental_yield": 5.0, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 79, "population": 230_000},
    ],
    "ES": [
        {"name": "Seville",       "avg_price_sqm": 2200, "avg_rental_yield": 5.8, "demand": "medium", "trend": "growth",   "risk": "low",    "score": 80, "population": 688_000},
        {"name": "Bilbao",        "avg_price_sqm": 3300, "avg_rental_yield": 5.3, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 79, "population": 346_000},
        {"name": "Palma de Mallorca","avg_price_sqm": 4200, "avg_rental_yield": 5.6, "demand": "high","trend": "growth",   "risk": "low",    "score": 83, "population": 416_000},
        {"name": "Alicante",      "avg_price_sqm": 2400, "avg_rental_yield": 6.2, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 84, "population": 337_000},
        {"name": "Marbella",      "avg_price_sqm": 5300, "avg_rental_yield": 5.0, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 82, "population": 148_000},
        {"name": "Ibiza",         "avg_price_sqm": 7300, "avg_rental_yield": 5.8, "demand": "high",   "trend": "stable",   "risk": "medium", "score": 80, "population": 50_000},
        {"name": "Granada",       "avg_price_sqm": 2000, "avg_rental_yield": 6.5, "demand": "medium", "trend": "growth",   "risk": "low",    "score": 82, "population": 232_000},
        {"name": "San Sebastián", "avg_price_sqm": 5500, "avg_rental_yield": 4.4, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 78, "population": 187_000},
    ],
    "CH": [
        {"name": "Basel",         "avg_price_sqm": 11500, "avg_rental_yield": 3.2, "demand": "medium","trend": "stable",   "risk": "low",    "score": 70, "population": 178_000},
        {"name": "Bern",          "avg_price_sqm": 10800, "avg_rental_yield": 3.0, "demand": "medium","trend": "stable",   "risk": "low",    "score": 70, "population": 134_000},
        {"name": "Lugano",        "avg_price_sqm": 9800,  "avg_rental_yield": 3.4, "demand": "medium","trend": "stable",   "risk": "low",    "score": 72, "population": 62_000},
        {"name": "Zermatt",       "avg_price_sqm": 13000, "avg_rental_yield": 3.6, "demand": "high",  "trend": "stable",   "risk": "low",    "score": 74, "population": 5_700},
        {"name": "St. Moritz",    "avg_price_sqm": 17000, "avg_rental_yield": 3.0, "demand": "high",  "trend": "stable",   "risk": "low",    "score": 70, "population": 5_200},
        {"name": "Montreux",      "avg_price_sqm": 11000, "avg_rental_yield": 3.3, "demand": "medium","trend": "stable",   "risk": "low",    "score": 71, "population": 27_000},
    ],
    "IT": [
        {"name": "Venice",        "avg_price_sqm": 4500, "avg_rental_yield": 5.0, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 78, "population": 257_000},
        {"name": "Bologna",       "avg_price_sqm": 3200, "avg_rental_yield": 5.4, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 82, "population": 392_000},
        {"name": "Naples",        "avg_price_sqm": 2400, "avg_rental_yield": 5.7, "demand": "medium", "trend": "stable",   "risk": "medium", "score": 75, "population": 967_000},
        {"name": "Turin",         "avg_price_sqm": 2300, "avg_rental_yield": 5.8, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 77, "population": 870_000},
        {"name": "Lake Como",     "avg_price_sqm": 6800, "avg_rental_yield": 4.6, "demand": "high",   "trend": "stable",   "risk": "low",    "score": 78, "population": 84_000},
        {"name": "Verona",        "avg_price_sqm": 2900, "avg_rental_yield": 5.5, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 78, "population": 257_000},
        {"name": "Genoa",         "avg_price_sqm": 1900, "avg_rental_yield": 6.4, "demand": "medium", "trend": "stable",   "risk": "medium", "score": 76, "population": 565_000},
        {"name": "Palermo",       "avg_price_sqm": 1700, "avg_rental_yield": 6.8, "demand": "medium", "trend": "growth",   "risk": "medium", "score": 76, "population": 663_000},
    ],
    "AE": [
        {"name": "Downtown Dubai","avg_price_sqm": 6100, "avg_rental_yield": 6.8, "demand": "high",   "trend": "growth",   "risk": "medium", "score": 88, "population": 18_000},
        {"name": "Palm Jumeirah", "avg_price_sqm": 7800, "avg_rental_yield": 6.5, "demand": "high",   "trend": "growth",   "risk": "medium", "score": 86, "population": 25_000},
        {"name": "Dubai Hills Estate","avg_price_sqm": 3400, "avg_rental_yield": 7.8, "demand": "high","trend": "growth",  "risk": "medium", "score": 89, "population": 17_000},
        {"name": "Arabian Ranches","avg_price_sqm": 2900, "avg_rental_yield": 7.0, "demand": "high",  "trend": "growth",   "risk": "medium", "score": 86, "population": 18_000},
        {"name": "Dubai Creek Harbour","avg_price_sqm": 3700,"avg_rental_yield": 7.5,"demand": "high","trend": "growth",   "risk": "medium", "score": 87, "population": 12_000},
        {"name": "Sharjah",       "avg_price_sqm": 1900, "avg_rental_yield": 7.4, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 78, "population": 1_400_000},
        {"name": "Ras Al Khaimah","avg_price_sqm": 1600, "avg_rental_yield": 8.0, "demand": "medium", "trend": "growth",   "risk": "medium", "score": 79, "population": 350_000},
    ],
    "PT": [
        {"name": "Cascais",       "avg_price_sqm": 6300, "avg_rental_yield": 5.0, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 84, "population": 215_000},
        {"name": "Faro",          "avg_price_sqm": 2700, "avg_rental_yield": 6.6, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 85, "population": 65_000},
        {"name": "Madeira",       "avg_price_sqm": 2800, "avg_rental_yield": 6.4, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 83, "population": 251_000},
        {"name": "Coimbra",       "avg_price_sqm": 1900, "avg_rental_yield": 7.2, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 81, "population": 144_000},
        {"name": "Braga",         "avg_price_sqm": 1800, "avg_rental_yield": 7.0, "demand": "medium", "trend": "growth",   "risk": "low",    "score": 81, "population": 192_000},
        {"name": "Évora",         "avg_price_sqm": 1700, "avg_rental_yield": 6.5, "demand": "medium", "trend": "stable",   "risk": "low",    "score": 78, "population": 56_000},
        {"name": "Lagos",         "avg_price_sqm": 3500, "avg_rental_yield": 6.8, "demand": "high",   "trend": "growth",   "risk": "low",    "score": 85, "population": 32_000},
    ],
}


def seed_more_cities(apps, schema_editor):
    Country = apps.get_model("geo", "Country")
    City = apps.get_model("geo", "City")

    for code, cities in EXTRA_CITIES.items():
        try:
            country = Country.objects.get(code=code)
        except Country.DoesNotExist:
            # Country isn't seeded yet — the regular `seed` command will run
            # later and re-create the schema; cities will be picked up on a
            # subsequent invocation of this migration if needed.
            continue

        for c in cities:
            City.objects.update_or_create(
                country=country,
                slug=slugify(c["name"]),
                defaults={
                    "name": c["name"],
                    "population": c.get("population"),
                    "avg_price_sqm": c.get("avg_price_sqm"),
                    "avg_rental_yield": c.get("avg_rental_yield"),
                    "demand": c.get("demand"),
                    "trend": c.get("trend"),
                    "risk": c.get("risk"),
                    "investment_score": c.get("score"),
                },
            )


def reverse(apps, schema_editor):
    # Non-destructive forward-only migration: keep the extra cities even if
    # someone rolls back, since users may have authored content tied to them.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("geo", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_more_cities, reverse),
    ]

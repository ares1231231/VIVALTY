"""Idempotent seed command.

Usage:
    python manage.py seed              # safe to re-run; updates baselines + adds missing items.
    python manage.py seed --reset      # wipes properties first.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.geo.models import City, Country
from apps.properties.models import (
    InvestmentTag,
    Property,
    PropertyImage,
    PropertyType,
)
from apps.users.models import Role, User


COUNTRIES = [
    {
        "code": "FR", "name": "France", "currency": "EUR", "flag_emoji": "🇫🇷",
        "base_roi_min": 3.5, "base_roi_max": 6.0, "base_rental_yield": 4.5,
        "base_demand": "high", "base_trend": "stable", "base_risk": "low",
        "summary": "Mature European market. Stable yields in Paris suburbs and growth pockets along the Côte d'Azur and Lyon.",
    },
    {
        "code": "GB", "name": "United Kingdom", "currency": "GBP", "flag_emoji": "🇬🇧",
        "base_roi_min": 3.0, "base_roi_max": 7.0, "base_rental_yield": 5.0,
        "base_demand": "high", "base_trend": "stable", "base_risk": "medium",
        "summary": "Deep liquidity in London; stronger yields in Manchester, Liverpool and Birmingham.",
    },
    {
        "code": "ES", "name": "Spain", "currency": "EUR", "flag_emoji": "🇪🇸",
        "base_roi_min": 4.0, "base_roi_max": 7.5, "base_rental_yield": 5.5,
        "base_demand": "high", "base_trend": "growth", "base_risk": "low",
        "summary": "Tourist demand on the coast and Madrid. Valencia and Málaga show strong growth.",
    },
    {
        "code": "CH", "name": "Switzerland", "currency": "CHF", "flag_emoji": "🇨🇭",
        "base_roi_min": 2.0, "base_roi_max": 4.0, "base_rental_yield": 3.0,
        "base_demand": "medium", "base_trend": "stable", "base_risk": "low",
        "summary": "Capital-preservation market. Low yields, very low risk; strong demand in Geneva and Zurich.",
    },
    {
        "code": "IT", "name": "Italy", "currency": "EUR", "flag_emoji": "🇮🇹",
        "base_roi_min": 3.5, "base_roi_max": 7.0, "base_rental_yield": 4.8,
        "base_demand": "medium", "base_trend": "stable", "base_risk": "medium",
        "summary": "Heterogeneous: Milan and Bologna see steady demand; tourist hotspots (Florence, Rome) yield well in short-let.",
    },
    {
        "code": "AE", "name": "United Arab Emirates", "currency": "AED", "flag_emoji": "🇦🇪",
        "base_roi_min": 6.0, "base_roi_max": 10.0, "base_rental_yield": 7.5,
        "base_demand": "high", "base_trend": "growth", "base_risk": "medium",
        "summary": "High yields in Dubai (Marina, JVC, Business Bay). Tax-free environment; cycle sensitivity to oil and global capital.",
    },
    {
        "code": "PT", "name": "Portugal", "currency": "EUR", "flag_emoji": "🇵🇹",
        "base_roi_min": 4.5, "base_roi_max": 8.0, "base_rental_yield": 5.8,
        "base_demand": "high", "base_trend": "growth", "base_risk": "low",
        "summary": "Lisbon and Porto see strong growth; Algarve is short-let driven. Golden visa changes have shifted demand inland.",
    },
]

CITIES = {
    "FR": [
        {"name": "Paris", "avg_price_sqm": 11500, "avg_rental_yield": 3.5, "demand": "high", "trend": "stable", "risk": "low", "score": 78, "population": 2_140_000},
        {"name": "Lyon", "avg_price_sqm": 5300, "avg_rental_yield": 4.6, "demand": "high", "trend": "growth", "risk": "low", "score": 80, "population": 522_000},
        {"name": "Nice", "avg_price_sqm": 5100, "avg_rental_yield": 4.2, "demand": "high", "trend": "stable", "risk": "low", "score": 76, "population": 342_000},
    ],
    "GB": [
        {"name": "London", "avg_price_sqm": 13500, "avg_rental_yield": 3.8, "demand": "high", "trend": "stable", "risk": "medium", "score": 75, "population": 8_982_000},
        {"name": "Manchester", "avg_price_sqm": 3800, "avg_rental_yield": 6.2, "demand": "high", "trend": "growth", "risk": "low", "score": 86, "population": 552_000},
        {"name": "Birmingham", "avg_price_sqm": 3200, "avg_rental_yield": 5.8, "demand": "medium", "trend": "growth", "risk": "low", "score": 82, "population": 1_141_000},
    ],
    "ES": [
        {"name": "Madrid", "avg_price_sqm": 4400, "avg_rental_yield": 5.0, "demand": "high", "trend": "growth", "risk": "low", "score": 84, "population": 3_223_000},
        {"name": "Barcelona", "avg_price_sqm": 4900, "avg_rental_yield": 4.7, "demand": "high", "trend": "stable", "risk": "low", "score": 81, "population": 1_620_000},
        {"name": "Valencia", "avg_price_sqm": 2400, "avg_rental_yield": 6.4, "demand": "high", "trend": "growth", "risk": "low", "score": 88, "population": 791_000},
        {"name": "Málaga", "avg_price_sqm": 2900, "avg_rental_yield": 6.0, "demand": "high", "trend": "growth", "risk": "low", "score": 85, "population": 578_000},
    ],
    "CH": [
        {"name": "Geneva", "avg_price_sqm": 14500, "avg_rental_yield": 2.9, "demand": "high", "trend": "stable", "risk": "low", "score": 70, "population": 203_000},
        {"name": "Zurich", "avg_price_sqm": 16000, "avg_rental_yield": 2.8, "demand": "high", "trend": "stable", "risk": "low", "score": 72, "population": 421_000},
        {"name": "Lausanne", "avg_price_sqm": 12000, "avg_rental_yield": 3.1, "demand": "medium", "trend": "stable", "risk": "low", "score": 68, "population": 140_000},
    ],
    "IT": [
        {"name": "Milan", "avg_price_sqm": 5200, "avg_rental_yield": 4.5, "demand": "high", "trend": "growth", "risk": "low", "score": 80, "population": 1_396_000},
        {"name": "Rome", "avg_price_sqm": 3500, "avg_rental_yield": 4.8, "demand": "high", "trend": "stable", "risk": "medium", "score": 76, "population": 2_873_000},
        {"name": "Florence", "avg_price_sqm": 4100, "avg_rental_yield": 5.6, "demand": "medium", "trend": "stable", "risk": "low", "score": 78, "population": 367_000},
    ],
    "AE": [
        {"name": "Dubai Marina", "avg_price_sqm": 4800, "avg_rental_yield": 7.8, "demand": "high", "trend": "growth", "risk": "medium", "score": 90, "population": 55_000},
        {"name": "Business Bay", "avg_price_sqm": 4100, "avg_rental_yield": 8.2, "demand": "high", "trend": "growth", "risk": "medium", "score": 88, "population": 30_000},
        {"name": "Jumeirah Village Circle", "avg_price_sqm": 2700, "avg_rental_yield": 9.1, "demand": "high", "trend": "growth", "risk": "medium", "score": 92, "population": 30_000},
        {"name": "Abu Dhabi", "avg_price_sqm": 3300, "avg_rental_yield": 6.5, "demand": "medium", "trend": "stable", "risk": "low", "score": 80, "population": 1_482_000},
    ],
    "PT": [
        {"name": "Lisbon", "avg_price_sqm": 5400, "avg_rental_yield": 5.4, "demand": "high", "trend": "growth", "risk": "low", "score": 86, "population": 545_000},
        {"name": "Porto", "avg_price_sqm": 3300, "avg_rental_yield": 6.1, "demand": "high", "trend": "growth", "risk": "low", "score": 88, "population": 232_000},
        {"name": "Algarve", "avg_price_sqm": 3100, "avg_rental_yield": 6.8, "demand": "high", "trend": "growth", "risk": "low", "score": 84, "population": 467_000},
    ],
}

TAGS = [
    ("High ROI", "emerald"),
    ("Luxury", "amber"),
    ("Emerging market", "sky"),
    ("Short-let friendly", "rose"),
    ("Capital preservation", "indigo"),
    ("New build", "lime"),
    ("Beachfront", "cyan"),
]

UNSPLASH = [
    "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1200",
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200",
    "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1200",
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1200",
    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200",
    "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=1200",
    "https://images.unsplash.com/photo-1572120360610-d971b9d7767c?w=1200",
    "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=1200",
    "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=1200",
]

PROPERTY_TYPES = [pt for pt, _ in PropertyType.choices]

DESCRIPTIONS = {
    "apartment": "Bright {br}-bedroom apartment in {city}, {area} m², featuring open-plan living, modern kitchen and access to local transit.",
    "villa": "Private villa in {city} with {br} bedrooms over {area} m². Garden, parking and high-end finishes.",
    "house": "Townhouse in {city}, {br} bedrooms, {area} m². Family layout with garden.",
    "commercial": "Commercial unit in {city}, {area} m². Suitable for retail or office use, strong footfall.",
    "land": "Building plot in {city}, {area} m². Permits pending; ideal for development.",
    "office": "Class-A office space in {city}, {area} m². Open floor plan, parking included.",
    "retail": "Street-level retail unit in {city}, {area} m². Long lease available.",
}


class Command(BaseCommand):
    help = "Seed Vivalty with target countries, cities, tags and demo properties."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--reset", action="store_true", help="Delete existing properties first.")
        parser.add_argument("--per-city", type=int, default=2, help="Demo properties per city.")

    @transaction.atomic
    def handle(self, *args, reset: bool = False, per_city: int = 2, **options):
        random.seed(42)

        if reset:
            self.stdout.write(self.style.WARNING("Wiping existing Property rows..."))
            Property.objects.all().delete()

        # --- Owner --------------------------------------------------------
        owner, created = User.objects.get_or_create(
            email="demo-owner@vivalty.app",
            defaults={
                "username": "demo-owner@vivalty.app",
                "first_name": "Demo",
                "last_name": "Owner",
                "role": Role.OWNER,
                "company_name": "Vivalty Demo Listings",
            },
        )
        if created:
            owner.set_password("vivalty-demo-pass")
            owner.save()
            self.stdout.write(self.style.SUCCESS("Created demo owner: demo-owner@vivalty.app / vivalty-demo-pass"))

        # --- Tags ---------------------------------------------------------
        tag_objs: dict[str, InvestmentTag] = {}
        for name, color in TAGS:
            tag, _ = InvestmentTag.objects.update_or_create(
                slug=slugify(name), defaults={"name": name, "color": color}
            )
            tag_objs[tag.slug] = tag

        # --- Countries + cities ------------------------------------------
        country_objs: dict[str, Country] = {}
        for c in COUNTRIES:
            obj, _ = Country.objects.update_or_create(
                code=c["code"],
                defaults={
                    "name": c["name"],
                    "currency": c["currency"],
                    "flag_emoji": c["flag_emoji"],
                    "base_roi_min": c["base_roi_min"],
                    "base_roi_max": c["base_roi_max"],
                    "base_rental_yield": c["base_rental_yield"],
                    "base_demand": c["base_demand"],
                    "base_trend": c["base_trend"],
                    "base_risk": c["base_risk"],
                    "summary": c["summary"],
                },
            )
            country_objs[c["code"]] = obj

        city_objs: list[City] = []
        for code, cities in CITIES.items():
            country = country_objs[code]
            for city in cities:
                obj, _ = City.objects.update_or_create(
                    country=country, slug=slugify(city["name"]),
                    defaults={
                        "name": city["name"],
                        "population": city["population"],
                        "avg_price_sqm": Decimal(str(city["avg_price_sqm"])),
                        "avg_rental_yield": Decimal(str(city["avg_rental_yield"])),
                        "demand": city["demand"],
                        "trend": city["trend"],
                        "risk": city["risk"],
                        "investment_score": city["score"],
                        "summary": f"{city['name']} — avg €/m² {city['avg_price_sqm']}, yield {city['avg_rental_yield']}%, score {city['score']}/100.",
                    },
                )
                city_objs.append(obj)

        # --- Properties ---------------------------------------------------
        added = 0
        for city in city_objs:
            country = city.country
            for i in range(per_city):
                ptype = random.choice([
                    PropertyType.APARTMENT, PropertyType.APARTMENT,
                    PropertyType.VILLA, PropertyType.HOUSE, PropertyType.COMMERCIAL,
                ])
                br = random.choice([1, 2, 3, 4]) if ptype != PropertyType.COMMERCIAL else None
                area = round(random.uniform(45, 320), 1)
                psqm = float(city.avg_price_sqm or 3000)
                price = round(area * psqm * random.uniform(0.85, 1.25), -2)
                title = f"{ptype.label} in {city.name} #{i + 1}"

                if Property.objects.filter(title=title, city=city).exists():
                    continue

                desc_tpl = DESCRIPTIONS.get(ptype, DESCRIPTIONS["apartment"])
                desc = desc_tpl.format(br=br or "open", area=area, city=city.name)

                prop = Property.objects.create(
                    owner=owner,
                    title=title,
                    description=desc,
                    property_type=ptype,
                    status="active",
                    price=Decimal(str(price)),
                    currency=country.currency,
                    country=country,
                    city=city,
                    address=f"{random.randint(1, 200)} Demo Street, {city.name}",
                    bedrooms=br,
                    bathrooms=random.choice([1, 2, 3]) if br else None,
                    area_sqm=Decimal(str(area)),
                    year_built=random.randint(1985, 2024),
                    contact_name="Vivalty Demo Desk",
                    contact_email="leads@vivalty.app",
                    contact_phone="+1 555 0100",
                    is_featured=(i == 0 and random.random() < 0.4),
                )
                # Images
                for j, url in enumerate(random.sample(UNSPLASH, k=3)):
                    PropertyImage.objects.create(property=prop, url=url, position=j)
                # Tags
                slugs = []
                if (city.investment_score or 0) >= 85:
                    slugs.append("high-roi")
                if "Dubai" in city.name or psqm < 3500:
                    slugs.append("emerging-market")
                if psqm > 9000:
                    slugs.append("luxury")
                if country.code == "PT" or "Algarve" in city.name:
                    slugs.append("short-let-friendly")
                if country.code == "CH":
                    slugs.append("capital-preservation")
                prop.tags.set(InvestmentTag.objects.filter(slug__in=slugs))
                added += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {len(country_objs)} countries, {len(city_objs)} cities, {added} new properties."
        ))

"""Upsert property rows from normalized listing dicts (JSON import / scraper)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils.text import slugify

from apps.geo.models import City, Country
from apps.properties.models import InvestmentTag, Property, PropertyImage, PropertyType
from apps.properties.services.scoring import upsert_metric
from apps.users.models import Role, User

DEFAULT_OWNER_EMAIL = "feeds@vivalty.app"


def get_or_create_feed_owner() -> User:
    owner, created = User.objects.get_or_create(
        email=DEFAULT_OWNER_EMAIL,
        defaults={
            "username": DEFAULT_OWNER_EMAIL,
            "first_name": "Vivalty",
            "last_name": "Feeds",
            "role": Role.OWNER,
            "company_name": "Vivalty Feeds",
        },
    )
    if created:
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
    return owner


def import_listing_rows(
    rows: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    owner: User | None = None,
) -> tuple[int, int]:
    """Import listings idempotently by ``listing_ref``. Returns (created, updated)."""
    if not rows:
        return 0, 0

    owner = owner or get_or_create_feed_owner()
    created_count = 0
    updated_count = 0

    for row in rows:
        listing_ref = row.get("listing_ref")
        if not listing_ref:
            raise ValueError("Each listing must include listing_ref.")

        country = Country.objects.filter(code=row["country_code"]).first()
        if not country:
            raise ValueError(
                f"Unknown country {row['country_code']} for {listing_ref}. Run seed first."
            )

        city_name = row.get("city_name") or country.name
        city = City.objects.filter(country=country, name=city_name).first()
        if not city:
            city = City.objects.filter(country=country).order_by("name").first()
        if not city:
            raise ValueError(f"No city for {country.code} ({listing_ref}). Run seed first.")

        ptype = row.get("property_type", "apartment")
        if ptype not in PropertyType.values:
            ptype = PropertyType.APARTMENT

        defaults = {
            "owner": owner,
            "title": (row.get("title") or listing_ref)[:200],
            "description": row.get("description", ""),
            "property_type": ptype,
            "status": row.get("status", "active"),
            "price": Decimal(str(row["price"])),
            "currency": row.get("currency") or country.currency,
            "country": country,
            "city": city,
            "address": row.get("address", ""),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "bedrooms": row.get("bedrooms"),
            "bathrooms": row.get("bathrooms"),
            "area_sqm": Decimal(str(row["area_sqm"])) if row.get("area_sqm") else None,
            "year_built": row.get("year_built"),
            "contact_name": row.get("contact_name", ""),
            "contact_email": row.get("contact_email", ""),
            "contact_phone": row.get("contact_phone", ""),
            "listing_agency": row.get("listing_agency", ""),
            "is_featured": bool(row.get("is_featured")),
            "is_premium": bool(row.get("is_premium")),
            "is_verified": bool(row.get("is_verified")),
        }

        if dry_run:
            continue

        prop, was_created = Property.objects.update_or_create(
            listing_ref=listing_ref,
            defaults=defaults,
        )
        if not prop.slug:
            base = slugify(f"{prop.title}-{city.name}")[:230]
            prop.slug = f"{base}-{prop.pk}"
            prop.save(update_fields=["slug"])

        prop.images.all().delete()
        for i, url in enumerate(row.get("images") or []):
            if url:
                PropertyImage.objects.create(property=prop, url=str(url)[:1000], position=i)

        tag_slugs = row.get("tags") or []
        if tag_slugs:
            prop.tags.set(InvestmentTag.objects.filter(slug__in=tag_slugs))

        upsert_metric(prop)

        if was_created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count

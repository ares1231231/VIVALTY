"""Import editorial curated listings from data/curated_listings.json.

These are hand-written flagship properties (not scraped from other portals).
Safe to re-run: upserts by ``listing_ref``.

Usage:
    python manage.py seed                          # countries + cities first
    python manage.py import_curated_listings       # add / update curated set
    python manage.py import_curated_listings --file path/to/custom.json
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.geo.models import City, Country
from apps.properties.models import InvestmentTag, Property, PropertyImage, PropertyType
from apps.properties.services.scoring import upsert_metric
from apps.users.models import Role, User

DEFAULT_FILE = Path(__file__).resolve().parents[4] / "data" / "curated_listings.json"


class Command(BaseCommand):
    help = "Import hand-curated flagship listings from JSON (idempotent by listing_ref)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--file",
            type=str,
            default=str(DEFAULT_FILE),
            help="Path to curated listings JSON (default: data/curated_listings.json).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print actions without writing to the database.",
        )

    @transaction.atomic
    def handle(self, *args, file: str, dry_run: bool = False, **options):
        path = Path(file)
        if not path.is_file():
            raise CommandError(f"File not found: {path}")

        with path.open(encoding="utf-8") as fh:
            rows = json.load(fh)
        if not isinstance(rows, list) or not rows:
            raise CommandError("JSON must be a non-empty array of listing objects.")

        owner, created = User.objects.get_or_create(
            email="editorial@vivalty.app",
            defaults={
                "username": "editorial@vivalty.app",
                "first_name": "Vivalty",
                "last_name": "Editorial",
                "role": Role.OWNER,
                "company_name": "Vivalty Premium",
            },
        )
        if created and not dry_run:
            owner.set_password("vivalty-editorial-pass")
            owner.save()
            self.stdout.write(
                self.style.SUCCESS(
                    "Created editorial owner: editorial@vivalty.app / vivalty-editorial-pass"
                )
            )

        created_count = 0
        updated_count = 0

        for row in rows:
            listing_ref = row.get("listing_ref")
            if not listing_ref:
                raise CommandError("Each listing must include listing_ref.")

            country = Country.objects.filter(code=row["country_code"]).first()
            if not country:
                raise CommandError(
                    f"Unknown country {row['country_code']} for {listing_ref}. "
                    "Run `python manage.py seed` first."
                )

            city = City.objects.filter(country=country, name=row["city_name"]).first()
            if not city:
                raise CommandError(
                    f"Unknown city {row['city_name']} ({country.code}) for {listing_ref}. "
                    "Run `python manage.py seed` first."
                )

            ptype = row.get("property_type", "apartment")
            if ptype not in PropertyType.values:
                raise CommandError(f"Invalid property_type '{ptype}' on {listing_ref}.")

            defaults = {
                "owner": owner,
                "title": row["title"],
                "description": row.get("description", ""),
                "property_type": ptype,
                "status": "active",
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
                "listing_agency": row.get("listing_agency", "Vivalty Premium"),
                "is_featured": bool(row.get("is_featured")),
                "is_premium": bool(row.get("is_premium")),
                "is_verified": bool(row.get("is_verified")),
            }

            if dry_run:
                exists = Property.objects.filter(listing_ref=listing_ref).exists()
                action = "update" if exists else "create"
                self.stdout.write(f"[dry-run] would {action} {listing_ref}: {row['title']}")
                continue

            prop, was_created = Property.objects.update_or_create(
                listing_ref=listing_ref,
                defaults=defaults,
            )
            if not prop.slug:
                base = slugify(f"{prop.title}-{city.name}")[:230]
                prop.slug = f"{base}-{prop.pk}"
                prop.save(update_fields=["slug"])

            # Replace images on each import so edits to JSON refresh galleries.
            prop.images.all().delete()
            for i, url in enumerate(row.get("images") or []):
                PropertyImage.objects.create(property=prop, url=url, position=i)

            tag_slugs = row.get("tags") or []
            if tag_slugs:
                prop.tags.set(InvestmentTag.objects.filter(slug__in=tag_slugs))

            upsert_metric(prop)

            if was_created:
                created_count += 1
            else:
                updated_count += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run OK — {len(rows)} listing(s) validated."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Curated import complete: {created_count} created, {updated_count} updated "
                f"(total active: {Property.objects.filter(status='active').count()})."
            )
        )

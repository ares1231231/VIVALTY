"""SEO helpers — JSON-LD, meta descriptions, breadcrumbs, marketplace copy."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from apps.properties.models import Property, Status


def _strip_text(value: str, max_len: int = 160) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def property_absolute_url(prop: Property) -> str:
    """Canonical public path for a listing (slug + pk when available)."""
    if prop.slug:
        return reverse(
            "web:property_detail_seo",
            kwargs={"slug": prop.slug, "pk": prop.pk},
        )
    return reverse("web:property_detail", kwargs={"pk": prop.pk})


def property_meta_description(prop: Property) -> str:
    if prop.description:
        return _strip_text(prop.description, 160)
    score = ""
    if (
        settings.SHOW_INVESTMENT_FEATURES
        and getattr(prop, "metric", None)
        and prop.metric.investment_score
    ):
        score = f" AI investment score {prop.metric.investment_score}/100."
    purpose = "for rent" if getattr(prop, "listing_purpose", "") == "rent" else "for sale"
    return (
        f"{prop.get_property_type_display()} {purpose} in {prop.city.name}, {prop.country.name}."
        f"{score} Price, photos and full details on Vivalty."
    )[:160]


def property_json_ld(prop: Property) -> str:
    site = settings.SITE_URL.rstrip("/")
    path = property_absolute_url(prop)
    url = f"{site}{path}"
    images: list[str] = []
    primary = prop.primary_image_url
    if primary:
        images.append(primary)
    try:
        for img in prop.images.all()[:6]:
            src = getattr(img, "url", None) or getattr(getattr(img, "image", None), "url", None)
            if src:
                abs_src = str(src)
                if abs_src.startswith("/") and not abs_src.startswith("//"):
                    abs_src = f"{site}{abs_src}"
                if abs_src not in images:
                    images.append(abs_src)
    except Exception:
        pass
    if not images:
        images = [f"{site}/static/img/og-image.png"]

    availability = "https://schema.org/InStock"
    if prop.status == Status.SOLD:
        availability = "https://schema.org/SoldOut"
    elif prop.status == Status.RENTED:
        availability = "https://schema.org/OutOfStock"
    elif prop.status != Status.ACTIVE:
        availability = "https://schema.org/Discontinued"

    residence_type = "Apartment"
    ptype = (prop.property_type or "").lower()
    if "villa" in ptype or "house" in ptype:
        residence_type = "House"
    elif "land" in ptype:
        residence_type = "LandParcel"
    elif "office" in ptype or "commercial" in ptype or "retail" in ptype:
        residence_type = "Place"

    listing: dict[str, Any] = {
        "@type": "RealEstateListing",
        "@id": f"{url}#listing",
        "name": prop.title,
        "description": property_meta_description(prop),
        "url": url,
        "image": images if len(images) > 1 else images[0],
        "datePosted": prop.created_at.isoformat() if prop.created_at else None,
        "dateModified": prop.updated_at.isoformat() if prop.updated_at else None,
        "offers": {
            "@type": "Offer",
            "price": str(prop.price),
            "priceCurrency": prop.currency or "EUR",
            "availability": availability,
            "url": url,
        },
        "address": {
            "@type": "PostalAddress",
            "streetAddress": prop.address or None,
            "addressLocality": prop.city.name,
            "addressCountry": prop.country.code,
        },
    }
    if prop.bedrooms:
        listing["numberOfRooms"] = prop.bedrooms
    if prop.area_sqm:
        listing["floorSize"] = {
            "@type": "QuantitativeValue",
            "value": float(prop.area_sqm),
            "unitCode": "MTK",
        }
    if prop.latitude is not None and prop.longitude is not None:
        listing["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(prop.latitude),
            "longitude": float(prop.longitude),
        }

    residence = {
        "@type": residence_type,
        "name": prop.title,
        "address": listing["address"],
    }
    if "geo" in listing:
        residence["geo"] = listing["geo"]

    crumbs = breadcrumb_json_ld(
        [
            ("Home", "/"),
            ("Marketplace", reverse("web:marketplace")),
            (prop.country.name, f"{reverse('web:marketplace')}?country={prop.country.code}"),
            (prop.title, path),
        ]
    )

    payload = {
        "@context": "https://schema.org",
        "@graph": [listing, residence, crumbs],
    }
    return json.dumps(payload, ensure_ascii=False)


def site_json_ld() -> str:
    site = settings.SITE_URL.rstrip("/")
    org: dict[str, Any] = {
        "@type": "Organization",
        "@id": f"{site}/#organization",
        "name": "Vivalty",
        "url": site,
        "logo": {
            "@type": "ImageObject",
            "url": f"{site}/static/img/og-image.png",
            "width": 1200,
            "height": 630,
        },
        "description": (
            "International real estate marketplace with curated listings "
            "across Europe and the UAE."
        ),
        "areaServed": [
            {"@type": "Country", "name": n}
            for n in (
                "France",
                "Portugal",
                "Spain",
                "Italy",
                "Switzerland",
                "United Arab Emirates",
                "United Kingdom",
            )
        ],
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": getattr(settings, "COMPANY_SUPPORT_EMAIL", "") or "hello@vivalty.com",
                "availableLanguage": ["English", "French", "Spanish", "Portuguese", "Italian"],
            }
        ],
    }
    same_as = [
        s
        for s in (
            getattr(settings, "SOCIAL_INSTAGRAM_URL", ""),
            getattr(settings, "SOCIAL_LINKEDIN_URL", ""),
            getattr(settings, "SOCIAL_X_URL", ""),
            getattr(settings, "SOCIAL_FACEBOOK_URL", ""),
        )
        if s
    ]
    if same_as:
        org["sameAs"] = same_as

    payload = {
        "@context": "https://schema.org",
        "@graph": [
            org,
            {
                "@type": "WebSite",
                "@id": f"{site}/#website",
                "name": "Vivalty",
                "url": site,
                "publisher": {"@id": f"{site}/#organization"},
                "inLanguage": "en",
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": f"{site}/marketplace/?search={{search_term_string}}",
                    },
                    "query-input": "required name=search_term_string",
                },
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def breadcrumb_json_ld(items: list[tuple[str, str]]) -> dict[str, Any]:
    """Build a BreadcrumbList dict (for embedding in @graph)."""
    site = settings.SITE_URL.rstrip("/")
    elements = []
    for i, (name, path) in enumerate(items, start=1):
        href = path if path.startswith("http") else f"{site}{path}"
        elements.append(
            {
                "@type": "ListItem",
                "position": i,
                "name": name,
                "item": href,
            }
        )
    return {
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def breadcrumbs_script(items: list[tuple[str, str]]) -> str:
    return json.dumps(
        {"@context": "https://schema.org", **breadcrumb_json_ld(items)},
        ensure_ascii=False,
    )


def marketplace_seo(
    *,
    country_name: str | None = None,
    country_code: str | None = None,
    city_name: str | None = None,
    property_type_label: str | None = None,
    total: int | None = None,
) -> tuple[str, str, str]:
    """Return (title, description, h1) for marketplace / filtered landings."""
    parts: list[str] = []
    if property_type_label:
        parts.append(property_type_label)
    else:
        parts.append("Homes")
    if city_name:
        parts.append(f"in {city_name}")
        if country_name:
            parts.append(f", {country_name}")
    elif country_name:
        parts.append(f"in {country_name}")
    else:
        parts.append("abroad")

    subject = " ".join(parts).replace(" ,", ",")
    h1 = subject if country_name or city_name or property_type_label else "Property listings"
    title = f"{subject} for sale & rent · Vivalty"
    if len(title) > 65:
        title = f"{subject} · Vivalty"[:65]

    count_bit = f"{total} verified listings" if total is not None else "Verified listings"
    if city_name and country_name:
        where = f"{city_name}, {country_name}"
    elif country_name:
        where = country_name
    else:
        where = "France, Portugal, Spain, Italy, Switzerland, the UAE and the UK"
    focus = property_type_label.lower() if property_type_label else "homes"
    desc = (
        f"{count_bit} — browse {focus} in {where}. "
        "Photos, prices and direct agency contact on Vivalty."
    )
    return title[:70], _strip_text(desc, 160), h1


def marketplace_item_list_json_ld(items: list[Property], page_url: str) -> str:
    """ItemList schema for marketplace result pages (max 12)."""
    site = settings.SITE_URL.rstrip("/")
    elements = []
    for i, prop in enumerate(items[:12], start=1):
        path = property_absolute_url(prop)
        elements.append(
            {
                "@type": "ListItem",
                "position": i,
                "url": f"{site}{path}",
                "name": prop.title,
            }
        )
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "url": page_url if page_url.startswith("http") else f"{site}{page_url}",
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }
    return json.dumps(payload, ensure_ascii=False)


def marketplace_filter_query(params) -> str:
    """Stable query string for secondary filters (excludes page)."""
    keep = {}
    for key in ("type", "search", "price_min", "price_max", "ordering", "beds", "purpose"):
        val = params.get(key) if hasattr(params, "get") else None
        if val:
            keep[key] = val
    return urlencode(keep)

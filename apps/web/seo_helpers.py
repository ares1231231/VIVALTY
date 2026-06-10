"""SEO helpers — JSON-LD and meta description builders."""

from __future__ import annotations

import json
import re
from html import unescape

from django.conf import settings
from django.urls import reverse

from apps.properties.models import Property


def _strip_text(value: str, max_len: int = 160) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def property_meta_description(prop: Property) -> str:
    if prop.description:
        return _strip_text(prop.description, 160)
    score = ""
    if getattr(prop, "metric", None) and prop.metric.investment_score:
        score = f" AI investment score {prop.metric.investment_score}/100."
    return (
        f"{prop.get_property_type_display()} for sale in {prop.city.name}, {prop.country.name}."
        f"{score} View price, yield and market data on Vivalty."
    )[:160]


def property_json_ld(prop: Property) -> str:
    site = settings.SITE_URL.rstrip("/")
    url = f"{site}{reverse('web:property_detail', kwargs={'pk': prop.pk})}"
    image = prop.primary_image_url or f"{site}/static/img/og-image.png"
    payload = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": prop.title,
        "description": property_meta_description(prop),
        "url": url,
        "image": image,
        "dateModified": prop.updated_at.isoformat() if prop.updated_at else None,
        "offers": {
            "@type": "Offer",
            "price": str(prop.price),
            "priceCurrency": prop.currency or "EUR",
            "availability": "https://schema.org/InStock",
        },
        "address": {
            "@type": "PostalAddress",
            "addressLocality": prop.city.name,
            "addressCountry": prop.country.name,
        },
    }
    if prop.bedrooms:
        payload["numberOfRooms"] = prop.bedrooms
    if prop.area_sqm:
        payload["floorSize"] = {
            "@type": "QuantitativeValue",
            "value": float(prop.area_sqm),
            "unitCode": "MTK",
        }
    return json.dumps(payload, ensure_ascii=False)


def site_json_ld() -> str:
    site = settings.SITE_URL.rstrip("/")
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "name": "Vivalty",
                "url": site,
                "logo": f"{site}/static/img/og-image.png",
                "description": (
                    "AI-powered international real estate platform for investors "
                    "across Europe and the UAE."
                ),
            },
            {
                "@type": "WebSite",
                "name": "Vivalty",
                "url": site,
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

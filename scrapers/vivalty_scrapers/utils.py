"""Parsing helpers for property listing spiders."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from itemadapter import ItemAdapter

_COUNTRY_FROM_PATH = {
    "portugal": "PT",
    "spain": "ES",
    "france": "FR",
    "united-kingdom": "GB",
    "uk": "GB",
    "italy": "IT",
    "switzerland": "CH",
    "united-arab-emirates": "AE",
    "uae": "AE",
    "dubai": "AE",
}

_TYPE_KEYWORDS = {
    "villa": "villa_house",
    "house": "villa_house",
    "moradia": "villa_house",
    "chalet": "villa_house",
    "townhouse": "villa_house",
    "apartment": "apartment",
    "flat": "apartment",
    "penthouse": "apartment",
    "studio": "studio",
    "t0": "studio",
    "commercial": "commercial",
    "office": "office",
    "land": "land",
    "plot": "land",
    "retail": "retail",
}


def country_code_from_url(url: str) -> str | None:
    path = urlparse(url).path.lower()
    for slug, code in _COUNTRY_FROM_PATH.items():
        if f"/{slug}/" in path or path.startswith(f"/{slug}"):
            return code
    return None


def parse_price(raw: str | int | float | None) -> tuple[float | None, str | None]:
    if raw is None:
        return None, None
    text = str(raw)
    currency = None
    if "£" in text or "GBP" in text.upper():
        currency = "GBP"
    elif "€" in text or "EUR" in text.upper():
        currency = "EUR"
    elif "CHF" in text.upper():
        currency = "CHF"
    elif "AED" in text.upper() or "د.إ" in text:
        currency = "AED"
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if not digits:
        return None, currency
    try:
        return float(digits), currency
    except ValueError:
        return None, currency


def infer_property_type(*texts: str | None) -> str:
    blob = " ".join(t for t in texts if t).lower()
    for keyword, ptype in _TYPE_KEYWORDS.items():
        if keyword in blob:
            return ptype
    return "apartment"


def extract_json_ld(response) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw in response.css('script[type="application/ld+json"]::text').getall():
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            blocks.append(data)
            graph = data.get("@graph")
            if isinstance(graph, list):
                blocks.extend(x for x in graph if isinstance(x, dict))
    return blocks


def listing_from_json_ld(
    blocks: list[dict[str, Any]],
    *,
    country_code: str,
    source_url: str,
    default_city: str,
    currency_default: str,
) -> dict[str, Any] | None:
    for block in blocks:
        types = block.get("@type") or ""
        if isinstance(types, list):
            type_set = {str(t).lower() for t in types}
        else:
            type_set = {str(types).lower()}

        if not type_set & {
            "product",
            "house",
            "apartment",
            "residence",
            "singlefamilyresidence",
            "realestatelisting",
            "offer",
            "place",
        }:
            continue

        title = block.get("name") or block.get("headline")
        description = block.get("description") or ""

        price_val = None
        currency = currency_default
        offers = block.get("offers")
        if isinstance(offers, dict):
            price_val = offers.get("price") or offers.get("lowPrice")
            currency = offers.get("priceCurrency") or currency
        elif block.get("price"):
            price_val = block.get("price")

        if price_val is None:
            continue

        try:
            price = float(price_val)
        except (TypeError, ValueError):
            parsed, cur = parse_price(str(price_val))
            if parsed is None:
                continue
            price = parsed
            currency = cur or currency

        address = block.get("address") or {}
        if isinstance(address, str):
            city_name = default_city
            street = address
        else:
            city_name = (
                address.get("addressLocality")
                or address.get("addressRegion")
                or default_city
            )
            street = address.get("streetAddress") or ""

        geo = block.get("geo") or {}
        lat = geo.get("latitude")
        lng = geo.get("longitude")

        images: list[str] = []
        img = block.get("image")
        if isinstance(img, str):
            images.append(img)
        elif isinstance(img, list):
            for entry in img:
                if isinstance(entry, str):
                    images.append(entry)
                elif isinstance(entry, dict) and entry.get("url"):
                    images.append(entry["url"])

        ref = block.get("sku") or block.get("productID")
        if not ref:
            ref = urlparse(source_url).path.rstrip("/").split("/")[-1]
        listing_ref = f"SCRAPE-{country_code}-{ref}"[:64]

        return {
            "listing_ref": listing_ref,
            "title": (title or listing_ref)[:200],
            "description": description[:5000] if description else "",
            "property_type": infer_property_type(title, description),
            "price": price,
            "currency": currency,
            "country_code": country_code,
            "city_name": str(city_name)[:120],
            "address": str(street)[:255],
            "latitude": lat,
            "longitude": lng,
            "bedrooms": _int_or_none(block.get("numberOfRooms")),
            "bathrooms": None,
            "area_sqm": _float_or_none(block.get("floorSize", {}).get("value") if isinstance(block.get("floorSize"), dict) else None),
            "images": images[:12],
            "source_url": source_url,
            "listing_agency": block.get("brand", {}).get("name") if isinstance(block.get("brand"), dict) else "",
            "is_verified": False,
        }
    return None


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def item_to_dict(item) -> dict[str, Any]:
    data = dict(ItemAdapter(item))
    data.pop("source_url", None)
    return data

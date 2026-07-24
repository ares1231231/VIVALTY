"""Fetch real listings from portals whose robots.txt permits listing pages.

Portals covered (one subcommand each):
    propertyfinder  UAE      — server-rendered __NEXT_DATA__ on search + detail
    bienici         France   — public realEstateAds.json endpoint (the same one
                               the site's own frontend calls, no auth)
    pisos           Spain    — server-rendered HTML + OpenGraph meta
    onthemarket     England  — server-rendered HTML + OpenGraph meta

Deliberately polite: sequential requests, delay between each, small default
batches. Every description keeps a source-URL attribution line.

Usage:
    python scrapers/portal_fetch.py propertyfinder --max 12 --output data/scraped/pf_ae.json
    python scrapers/portal_fetch.py bienici --max 12 --output data/scraped/bienici_fr.json
    python scrapers/portal_fetch.py pisos --city madrid --max 8 --output data/scraped/pisos_es.json
    python scrapers/portal_fetch.py onthemarket --area london --max 10 --output data/scraped/otm_gb.json
    python manage.py scrape_listings --import-only <output.json>

Output rows match apps.properties.services.listing_import.import_listing_rows.
"""

from __future__ import annotations

import argparse
import html as html_lib
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Windows consoles default to cp1252; listing titles are full of accents.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,fr,es;q=0.8",
}
REQUEST_DELAY_SECONDS = 1.5
SQFT_TO_SQM = 0.092903


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def next_data(html: str) -> dict | None:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        html,
        re.S,
    )
    return json.loads(match.group(1)) if match else None


def meta(html: str, name: str) -> str:
    match = re.search(
        rf'<meta (?:property|name)="{re.escape(name)}" content="([^"]*)"', html
    )
    return html_lib.unescape(match.group(1)) if match else ""


def as_int(value) -> int | None:
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- propertyfinder

PF_BASE = "https://www.propertyfinder.ae"


def pf_city(full_name: str) -> str:
    if "abu dhabi" in full_name.lower():
        return "Abu Dhabi"
    if "sharjah" in full_name.lower():
        return "Sharjah"
    return "Dubai"


def fetch_propertyfinder(args) -> list[dict]:
    # l=1 restricts to Dubai; omit for country-wide results.
    loc = f"&l={args.location}" if args.location else ""
    search = f"{PF_BASE}/en/search?c=1&fu=0&ob=mr{loc}"
    html = fetch(search)
    urls = list(dict.fromkeys(re.findall(r"(/en/plp/buy/[^\"\\\s]+\.html)", html)))
    print(f"Found {len(urls)} detail URLs; fetching up to {args.max}.")

    rows: list[dict] = []
    for path in urls:
        if len(rows) >= args.max:
            break
        url = PF_BASE + path
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            data = next_data(fetch(url))
            prop = data["props"]["pageProps"]["propertyResult"]["property"]
        except Exception as exc:  # noqa: BLE001 — one bad advert must not kill the batch
            print(f"  skip {url} ({exc})")
            continue

        price = (prop.get("price") or {}).get("value")
        if not price:
            print(f"  skip {url} (no price)")
            continue

        location = prop.get("location") or {}
        coords = location.get("coordinates") or {}
        size = prop.get("size") or {}
        area_sqm = None
        if size.get("value"):
            area_sqm = round(float(size["value"]) * (SQFT_TO_SQM if size.get("unit") == "sqft" else 1), 1)

        images = []
        for img in (prop.get("images") or {}).get("property") or []:
            best = img.get("full") or img.get("medium")
            if best:
                images.append(best)

        description = (prop.get("description") or "").strip()
        description += f"\n\nSource: propertyfinder.ae — {url}"

        agent = (prop.get("agent") or {}).get("name") or ""
        broker = (prop.get("broker") or {}).get("name") or ""

        rows.append({
            "listing_ref": f"PF-AE-{prop.get('id')}",
            "title": (prop.get("title") or "").strip()[:200],
            "description": description[:5000],
            "property_type": "apartment" if prop.get("property_type_id") in (1, None) else "house",
            "price": float(price),
            "currency": (prop.get("price") or {}).get("currency") or "AED",
            "country_code": "AE",
            "city_name": pf_city(location.get("full_name") or ""),
            "address": (location.get("full_name") or "")[:250],
            "latitude": coords.get("lat"),
            "longitude": coords.get("lon"),
            "bedrooms": as_int(prop.get("bedrooms")),
            "bathrooms": as_int(prop.get("bathrooms")),
            "area_sqm": area_sqm,
            "year_built": None,
            "contact_name": agent,
            "contact_email": "",
            "contact_phone": "",
            "listing_agency": broker,
            "is_featured": False,
            "is_premium": False,
            "is_verified": False,
            "tags": [],
            "images": images[:8],
            "source_url": url,
        })
        print(f"  ok   {rows[-1]['listing_ref']}: {rows[-1]['title'][:66]} — AED {price:,.0f}")
    return rows


# ---------------------------------------------------------------- bienici

BIENICI_TYPE_FR = {"flat": "appartement", "house": "maison"}


def fetch_bienici(args) -> list[dict]:
    filters = {
        "size": max(args.max * 2, 24),
        "from": 0,
        "filterType": "buy",
        "propertyType": ["flat", "house"],
        "page": 1,
        "resultsPerPage": max(args.max * 2, 24),
        "onTheMarket": [True],
        "minPrice": 150000,
        "sortBy": "publicationDate",
        "sortOrder": "desc",
    }
    if args.zone:
        filters["zoneIdsByTypes"] = {"zoneIds": [args.zone]}
    url = "https://www.bienici.com/realEstateAds.json?filters=" + urllib.parse.quote(json.dumps(filters))
    ads = json.loads(fetch(url)).get("realEstateAds") or []
    print(f"API returned {len(ads)} ads; keeping up to {args.max}.")

    rows: list[dict] = []
    for ad in ads:
        if len(rows) >= args.max:
            break
        price = ad.get("price")
        if not price or not ad.get("photos"):
            continue

        city_raw = ad.get("city") or ""
        city = re.sub(r"\s+\d+e?r?\b.*$", "", city_raw).strip() or city_raw

        type_fr = BIENICI_TYPE_FR.get(ad.get("propertyType"), "appartement")
        city_slug = re.sub(r"[^a-z0-9]+", "-", city_raw.lower()).strip("-")
        source_url = f"https://www.bienici.com/annonce/{ad.get('adTypeFR', 'vente')}/{city_slug}/{type_fr}/{ad.get('id')}"

        images = [p.get("url_photo") or p.get("url") for p in ad.get("photos") or []]
        images = [i for i in images if i][:8]

        description = (ad.get("description") or "").strip()
        description += f"\n\nSource: bienici.com — {source_url}"

        blur = (ad.get("blurInfo") or {}).get("position") or {}

        rows.append({
            "listing_ref": f"BI-FR-{ad.get('id')}",
            "title": (ad.get("title") or "").strip()[:200] or f"{type_fr.title()} à {city}",
            "description": description[:5000],
            "property_type": "house" if ad.get("propertyType") == "house" else "apartment",
            "price": float(price),
            "currency": "EUR",
            "country_code": "FR",
            "city_name": city,
            "address": f"{city_raw} {ad.get('postalCode') or ''}".strip(),
            "latitude": blur.get("lat"),
            "longitude": blur.get("lon"),
            "bedrooms": as_int(ad.get("bedroomsQuantity")),
            "bathrooms": as_int(ad.get("bathroomsQuantity")),
            "area_sqm": float(ad["surfaceArea"]) if ad.get("surfaceArea") else None,
            "year_built": None,
            "contact_name": ad.get("accountDisplayName") or "",
            "contact_email": "",
            "contact_phone": "",
            "listing_agency": ad.get("accountDisplayName") or "",
            "is_featured": False,
            "is_premium": False,
            "is_verified": False,
            "tags": [],
            "images": images,
            "source_url": source_url,
        })
        print(f"  ok   {rows[-1]['listing_ref']}: {rows[-1]['title'][:66]} — €{price:,.0f}")
    return rows


# ---------------------------------------------------------------- pisos.com

PISOS_BASE = "https://www.pisos.com"
PISOS_CITY_NAME = {"madrid": "Madrid", "barcelona": "Barcelona", "valencia": "Valencia", "malaga": "Malaga"}


def parse_spanish_number(text: str) -> float | None:
    cleaned = text.replace(".", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_pisos(args) -> list[dict]:
    search = f"{PISOS_BASE}/venta/pisos-{args.city}/"
    html = fetch(search)
    urls = list(dict.fromkeys(re.findall(r'href="(/comprar/[^"]+_\d+/)"', html)))
    print(f"Found {len(urls)} detail URLs; fetching up to {args.max}.")

    rows: list[dict] = []
    for path in urls:
        if len(rows) >= args.max:
            break
        url = PISOS_BASE + path
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            dhtml = fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {url} ({exc})")
            continue

        og_title = meta(dhtml, "og:title")
        # "Piso en venta en Calle X, cerca de Y en Barrio por 1.600.000 €"
        price_match = re.search(r"por\s+([\d.,]+)\s*€", og_title)
        if not price_match:
            print(f"  skip {url} (no price in og:title)")
            continue
        price = parse_spanish_number(price_match.group(1))
        if not price or price < 30000:
            print(f"  skip {url} (implausible price)")
            continue

        title = og_title.split(" por ")[0].strip()
        address_match = re.search(r"venta en (.+?)(?: por |$)", og_title)
        address = address_match.group(1).strip() if address_match else ""

        images = list(dict.fromkeys(re.findall(r'(https://fotos\.imghs\.net/xl-wp/[^"\s\\]+\.jpg)', dhtml)))

        area_match = re.search(r"([\d.]+)\s*m[²2]", dhtml)
        rooms_match = re.search(r"(\d+)\s*hab", dhtml)
        baths_match = re.search(r"(\d+)\s*baño", dhtml)

        slug = path.split("/")[2]
        ptype = "house" if slug.startswith(("casa", "chalet", "finca")) else "apartment"

        description = meta(dhtml, "og:description").strip()
        description += f"\n\nSource: pisos.com — {url}"

        ref = path.rstrip("/").rsplit("-", 1)[-1]
        rows.append({
            "listing_ref": f"PIS-ES-{ref}",
            "title": title[:200],
            "description": description[:5000],
            "property_type": ptype,
            "price": price,
            "currency": "EUR",
            "country_code": "ES",
            "city_name": PISOS_CITY_NAME.get(args.city, args.city.title()),
            "address": address[:250],
            "latitude": None,
            "longitude": None,
            "bedrooms": as_int(rooms_match.group(1)) if rooms_match else None,
            "bathrooms": as_int(baths_match.group(1)) if baths_match else None,
            "area_sqm": parse_spanish_number(area_match.group(1)) if area_match else None,
            "year_built": None,
            "contact_name": "",
            "contact_email": "",
            "contact_phone": "",
            "listing_agency": "",
            "is_featured": False,
            "is_premium": False,
            "is_verified": False,
            "tags": [],
            "images": images[:8],
            "source_url": url,
        })
        print(f"  ok   {rows[-1]['listing_ref']}: {title[:66]} — €{price:,.0f}")
    return rows


# ---------------------------------------------------------------- onthemarket

OTM_BASE = "https://www.onthemarket.com"
OTM_AREA_CITY = {"london": "London", "manchester": "Manchester", "liverpool": "Liverpool", "edinburgh": "Edinburgh"}


def fetch_onthemarket(args) -> list[dict]:
    search = f"{OTM_BASE}/for-sale/property/{args.area}/"
    html = fetch(search)
    urls = list(dict.fromkeys(re.findall(r'href="(/details/\d+/?)"', html)))
    print(f"Found {len(urls)} detail URLs; fetching up to {args.max}.")

    rows: list[dict] = []
    for path in urls:
        if len(rows) >= args.max:
            break
        url = OTM_BASE + path
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            dhtml = fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {url} ({exc})")
            continue

        og_title = meta(dhtml, "og:title")
        if re.search(r"shared ownership|\bFMV\b|\bPlot\b", og_title, re.I):
            # Shared-ownership plots list a fractional price, not the full value.
            print(f"  skip {url} (shared ownership / plot)")
            continue
        price_match = re.search(r"£([\d,]+)", dhtml)
        if not price_match:
            print(f"  skip {url} (no price)")
            continue
        price = float(price_match.group(1).replace(",", ""))
        if price < 30000:
            print(f"  skip {url} (implausible price)")
            continue

        beds_match = re.search(r"(\d+)\s*bed", og_title, re.I) or re.search(r"(\d+)\s*bed", dhtml, re.I)
        title_beds_match = re.search(r"(\d+)\s*bed", og_title, re.I)
        baths_match = re.search(r"(\d+)\s*bath", dhtml, re.I)
        sqft_match = re.search(r"([\d,]+)\s*sq\s*ft", dhtml, re.I)
        area_sqm = None
        if sqft_match:
            sqft = parse_spanish_number(sqft_match.group(1).replace(",", ""))
            area_sqm = round(sqft * SQFT_TO_SQM, 1) if sqft else None

        images = list(dict.fromkeys(re.findall(r'(https://media\.onthemarket\.com/properties/\d+/[^"\s\\]+\.(?:jpg|jpeg|webp))', dhtml)))

        ptype = "house" if re.search(r"\b(house|cottage|bungalow|villa)\b", og_title, re.I) else "apartment"

        description = meta(dhtml, "og:description").strip()
        description += f"\n\nSource: onthemarket.com — {url}"

        title = re.sub(r"\s*for sale.*$", "", og_title).strip()
        address = title
        if title_beds_match:
            address = title[: title_beds_match.start()].strip().rstrip(",")

        ref = re.search(r"/details/(\d+)", path).group(1)
        rows.append({
            "listing_ref": f"OTM-GB-{ref}",
            "title": (title or f"Property {ref}")[:200],
            "description": description[:5000],
            "property_type": ptype,
            "price": price,
            "currency": "GBP",
            "country_code": "GB",
            "city_name": OTM_AREA_CITY.get(args.area, args.area.title()),
            "address": address[:250],
            "latitude": None,
            "longitude": None,
            "bedrooms": as_int(beds_match.group(1)) if beds_match else None,
            "bathrooms": as_int(baths_match.group(1)) if baths_match else None,
            "area_sqm": area_sqm,
            "year_built": None,
            "contact_name": "",
            "contact_email": "",
            "contact_phone": "",
            "listing_agency": "",
            "is_featured": False,
            "is_premium": False,
            "is_verified": False,
            "tags": [],
            "images": images[:8],
            "source_url": url,
        })
        print(f"  ok   {rows[-1]['listing_ref']}: {og_title[:66]} — £{price:,.0f}")
    return rows


# ---------------------------------------------------------------- main

PORTALS = {
    "propertyfinder": fetch_propertyfinder,
    "bienici": fetch_bienici,
    "pisos": fetch_pisos,
    "onthemarket": fetch_onthemarket,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("portal", choices=sorted(PORTALS))
    parser.add_argument("--max", type=int, default=10, help="Max listings to fetch (default: 10).")
    parser.add_argument("--city", default="madrid", help="pisos.com city slug (default: madrid).")
    parser.add_argument("--area", default="london", help="onthemarket area slug (default: london).")
    parser.add_argument("--zone", default="-7444", help="bienici zone id (default: -7444 = Paris). Empty = all France.")
    parser.add_argument("--location", default="", help="propertyfinder location id (1 = Dubai). Empty = country-wide.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    rows = PORTALS[args.portal](args)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {len(rows)} listing(s) to {output}")


if __name__ == "__main__":
    main()

"""Fetch real listings from imovirtual.com (OLX Group) into import-ready JSON.

Imovirtual's robots.txt allows crawling advert pages (/pt/anuncio/...) for
generic user agents. This fetcher is deliberately polite: sequential requests
with a delay, a small default batch, and it only reads the server-rendered
__NEXT_DATA__ payload — no API abuse. Developments without a unit price are
skipped; every imported description keeps a source-URL attribution line.

Usage:
    python scrapers/imovirtual_fetch.py --district lisboa --max 8
    python manage.py scrape_listings --import-only data/scraped/imovirtual_pt.json

The output rows match apps.properties.services.listing_import.import_listing_rows.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "scraped" / "imovirtual_pt.json"

BASE = "https://www.imovirtual.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt,en;q=0.8",
}
REQUEST_DELAY_SECONDS = 1.5

# Imovirtual province slug -> Vivalty City name (city rows auto-exist after seed;
# listing_import falls back to the country's first city for unknown names).
PROVINCE_TO_CITY = {
    "lisboa": "Lisbon",
    "porto": "Porto",
    "faro": "Faro",
    "braga": "Braga",
    "coimbra": "Coimbra",
    "evora": "Évora",
    "ilha-da-madeira": "Madeira",
}

PROPERTY_TYPE_MAP = {
    "flat": "apartment",
    "apartamento": "apartment",
    "studio": "studio",
    "t0": "studio",
    "house": "villa_house",
    "moradia": "villa_house",
    "villa": "villa_house",
    "terrain": "land",
    "terreno": "land",
    "commercial_property": "commercial",
    "office": "office",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def extract_next_data(html: str) -> dict | None:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        html,
        re.S,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def advert_urls_from_search(district: str, property_type: str) -> list[str]:
    url = f"{BASE}/pt/resultados/comprar/{property_type}/{district}"
    html = fetch(url)
    hrefs = re.findall(r'href="(/pt/anuncio/[a-zA-Z0-9\-]+-ID[a-zA-Z0-9]+)"', html)
    hrefs += re.findall(r'"(https://www\.imovirtual\.com/pt/anuncio/[a-zA-Z0-9\-]+-ID[a-zA-Z0-9]+)"', html)
    urls: list[str] = []
    for href in hrefs:
        full = href if href.startswith("http") else BASE + href
        if full not in urls:
            urls.append(full)
    return urls


def characteristic(ad: dict, key: str) -> str | None:
    for c in ad.get("characteristics") or []:
        if c.get("key") == key:
            return c.get("value")
    return None


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def row_from_advert(url: str) -> dict | None:
    data = extract_next_data(fetch(url))
    if not data:
        return None
    ad = (data.get("props", {}).get("pageProps") or {}).get("ad") or {}
    if not ad:
        return None

    price = (ad.get("price") or {}).get("value") or characteristic(ad, "price")
    if not price:
        # Developments / price-on-request adverts can't be shown with a price tag.
        return None

    target = ad.get("target") or {}
    province = (target.get("Province") or "").lower()
    city_name = PROVINCE_TO_CITY.get(province, "Lisbon")

    ptype_raw = (target.get("ProperType") or "").lower()
    ptype = PROPERTY_TYPE_MAP.get(ptype_raw, "apartment")

    location = ad.get("location") or {}
    coords = location.get("coordinates") or {}
    street = ((location.get("address") or {}).get("street") or {}).get("name") or ""

    images = []
    for img in ad.get("images") or []:
        best = img.get("large") or img.get("medium") or img.get("small")
        if best:
            images.append(best)
    images = images[:8]

    owner = ad.get("owner") or {}
    agency = (ad.get("agency") or {}).get("name") or owner.get("name") or ""
    phones = owner.get("phones") or []

    description = strip_html(ad.get("description") or "")
    description += f"\n\nSource: imovirtual.com — {url}"

    def as_int(value):
        try:
            return int(float(str(value).replace(",", ".")))
        except (TypeError, ValueError):
            return None

    area = characteristic(ad, "m") or target.get("Area")
    bathrooms = characteristic(ad, "bathrooms_num") or (target.get("Bathrooms_num") or [None])[0]
    year = characteristic(ad, "build_year") or target.get("Build_year")

    # Portuguese typology in the title (T2 = 2 bedrooms) is more reliable than
    # rooms_num, which counts total rooms (bedrooms + living room).
    title = ad.get("title") or ""
    typology = re.search(r"\bT(\d+)\b", title)
    if typology:
        bedrooms = int(typology.group(1))
    else:
        rooms = as_int(characteristic(ad, "rooms_num") or (target.get("Rooms_num") or [None])[0])
        bedrooms = max(rooms - 1, 1) if rooms else None

    return {
        "listing_ref": f"IMV-PT-{ad.get('publicId') or ad.get('id')}",
        "title": (ad.get("title") or "").strip()[:200],
        "description": description[:5000],
        "property_type": ptype,
        "price": float(price),
        "currency": (ad.get("price") or {}).get("currency") or "EUR",
        "country_code": "PT",
        "city_name": city_name,
        "address": street,
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "bedrooms": bedrooms,
        "bathrooms": as_int(bathrooms),
        "area_sqm": float(str(area).replace(",", ".")) if area else None,
        "year_built": as_int(year),
        "contact_name": owner.get("name") or "",
        "contact_email": "",
        "contact_phone": phones[0] if phones else "",
        "listing_agency": agency,
        "is_featured": False,
        "is_premium": False,
        "is_verified": False,
        "tags": [],
        "images": images,
        "source_url": url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", default="lisboa", help="Imovirtual district slug (default: lisboa).")
    parser.add_argument("--type", default="apartamento", help="Property type slug (default: apartamento).")
    parser.add_argument("--max", type=int, default=8, help="Max adverts to fetch (default: 8).")
    parser.add_argument("--output", default=str(OUTPUT_FILE), help="Output JSON path.")
    args = parser.parse_args()

    print(f"Searching {args.type} in {args.district} ...")
    urls = advert_urls_from_search(args.district, args.type)
    print(f"Found {len(urls)} advert URLs; fetching up to {args.max}.")

    rows: list[dict] = []
    for url in urls:
        if len(rows) >= args.max:
            break
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            row = row_from_advert(url)
        except Exception as exc:  # noqa: BLE001 — one bad advert must not kill the batch
            print(f"  skip {url} ({exc})")
            continue
        if row:
            rows.append(row)
            print(f"  ok   {row['listing_ref']}: {row['title'][:70]} — €{row['price']:,.0f}")
        else:
            print(f"  skip {url} (no unit price — likely a development)")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {len(rows)} listing(s) to {output}")


if __name__ == "__main__":
    main()

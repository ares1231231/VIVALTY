"""Kyero.com listing spider — crawls sitemap → property pages → JSON-LD.

Requires network access (Cloudflare may block datacenter IPs; use SCRAPER_PROXY
or run from a residential connection).
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import scrapy
import yaml

from vivalty_scrapers.items import ListingItem
from vivalty_scrapers.utils import (
    country_code_from_url,
    extract_json_ld,
    listing_from_json_ld,
    parse_price,
)


class KyeroSpider(scrapy.Spider):
    name = "kyero"
    allowed_domains = ["kyero.com", "www.kyero.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 8.0,
    }

    def __init__(
        self,
        country: str = "PT",
        max_items: str = "100",
        feeds_file: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.country_code = country.upper()
        self.max_items = int(max_items)
        self.feeds_file = feeds_file
        self._count = 0
        self._cfg = self._load_feeds()

    def _load_feeds(self) -> dict:
        path = self.feeds_file
        if not path:
            path = str(
                scrapy.utils.project.get_project_settings().get("VIVALTY_FEEDS_FILE")
            )
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    async def start(self):
        country_cfg = self._cfg["countries"].get(self.country_code)
        if not country_cfg:
            raise ValueError(f"No feed config for country {self.country_code}")

        location = country_cfg["kyero_location"]
        sitemap_url = "https://www.kyero.com/sitemap/root.xml"
        yield scrapy.Request(
            sitemap_url,
            callback=self.parse_sitemap_index,
            meta={"location_slug": location, "country_cfg": country_cfg},
            dont_filter=True,
        )

    def parse_sitemap_index(self, response):
        location_slug = response.meta["location_slug"]
        country_cfg = response.meta["country_cfg"]

        # Follow child sitemaps that mention the country slug.
        for href in response.css("loc::text").getall():
            if location_slug in href.lower():
                yield scrapy.Request(
                    href,
                    callback=self.parse_sitemap_urls,
                    meta={
                        "location_slug": location_slug,
                        "country_cfg": country_cfg,
                    },
                )

        # Also harvest property links directly from index if present.
        for href in response.css("loc::text").getall():
            if self._is_property_url(href, location_slug):
                yield from self._schedule_property(
                    href, country_cfg, response.request.headers
                )

    def parse_sitemap_urls(self, response):
        country_cfg = response.meta["country_cfg"]
        location_slug = response.meta["location_slug"]

        for href in response.css("loc::text").getall():
            if self._count >= self.max_items:
                return
            if self._is_property_url(href, location_slug):
                yield from self._schedule_property(
                    href, country_cfg, response.request.headers
                )
            elif href.endswith(".xml"):
                yield scrapy.Request(
                    href,
                    callback=self.parse_sitemap_urls,
                    meta=response.meta,
                )

    def _is_property_url(self, url: str, location_slug: str) -> bool:
        lower = url.lower()
        return (
            "kyero.com" in lower
            and f"/{location_slug}/" in lower
            and "/property/" in lower
        )

    def _schedule_property(self, url, country_cfg, headers):
        if self._count >= self.max_items:
            return
        self._count += 1
        yield scrapy.Request(
            url,
            callback=self.parse_property,
            meta={"country_cfg": country_cfg},
        )

    def parse_property(self, response):
        if response.status >= 400:
            self.logger.warning("Skip %s (%s)", response.url, response.status)
            return

        country_cfg = response.meta["country_cfg"]
        country_code = self.country_code
        default_city = country_cfg.get("default_city", country_cfg["name"])
        currency = country_cfg.get("currency", "EUR")

        blocks = extract_json_ld(response)
        row = listing_from_json_ld(
            blocks,
            country_code=country_code,
            source_url=response.url,
            default_city=default_city,
            currency_default=currency,
        )

        if not row:
            row = self._parse_html_fallback(response, country_cfg)

        if not row or not row.get("price"):
            return

        item = ListingItem()
        for key, value in row.items():
            if key in item.fields:
                item[key] = value
        yield item

    def _parse_html_fallback(self, response, country_cfg) -> dict | None:
        title = (
            response.css("h1::text").get()
            or response.css('meta[property="og:title"]::attr(content)').get()
            or response.css("title::text").get()
        )
        if not title:
            return None

        desc = (
            response.css('meta[property="og:description"]::attr(content)').get()
            or response.css('meta[name="description"]::attr(content)').get()
            or ""
        )

        price_text = (
            response.css('[class*="price"]::text').get()
            or response.css('[data-testid="price"]::text').get()
            or ""
        )
        price, currency = parse_price(price_text)
        if price is None:
            # Try embedded reference in page text
            match = re.search(r"€\s*([\d.,]+)", response.text)
            if match:
                price, currency = parse_price("€" + match.group(1))
        if price is None:
            return None

        images = response.css('meta[property="og:image"]::attr(content)').getall()
        images += [
            urljoin(response.url, src)
            for src in response.css("img::attr(src)").getall()
            if src and ("property" in src or "photo" in src or "image" in src)
        ]
        images = list(dict.fromkeys(images))[:12]

        slug = response.url.rstrip("/").split("/")[-1]
        listing_ref = f"KYERO-{self.country_code}-{slug}"[:64]

        city = country_cfg.get("default_city")
        breadcrumb = response.css('[class*="breadcrumb"] a::text').getall()
        if len(breadcrumb) >= 2:
            city = breadcrumb[-2].strip() or city

        return {
            "listing_ref": listing_ref,
            "title": title.strip()[:200],
            "description": desc.strip()[:5000],
            "property_type": "apartment",
            "price": price,
            "currency": currency or country_cfg.get("currency", "EUR"),
            "country_code": self.country_code,
            "city_name": city,
            "address": "",
            "images": images,
            "source_url": response.url,
            "is_verified": False,
        }

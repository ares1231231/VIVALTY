"""Generic spider for authorized listing index pages (JSON-LD on detail pages)."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import scrapy
import yaml

from vivalty_scrapers.items import ListingItem
from vivalty_scrapers.utils import (
    country_code_from_url,
    extract_json_ld,
    listing_from_json_ld,
)


class JsonLdSpider(scrapy.Spider):
    name = "json_ld"
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
    }

    def __init__(
        self,
        country: str = "PT",
        max_items: str = "100",
        feeds_file: str | None = None,
        start_url: str | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.country_code = country.upper()
        self.max_items = int(max_items)
        self.feeds_file = feeds_file
        self.start_url = start_url
        self._seen: set[str] = set()
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
        country_cfg = self._cfg["countries"][self.country_code]
        urls = []
        if self.start_url:
            urls.append(self.start_url)
        urls.extend(self._cfg.get("json_ld_start_urls", {}).get(self.country_code, []))

        if not urls:
            raise ValueError(
                f"No start URLs for {self.country_code}. "
                "Set json_ld_start_urls in scrapers/feeds.yaml or pass -a start_url=..."
            )

        for url in urls:
            yield scrapy.Request(
                url, callback=self.parse_index, meta={"country_cfg": country_cfg}
            )

    def parse_index(self, response):
        country_cfg = response.meta["country_cfg"]
        links = set(response.css("a::attr(href)").getall())

        for href in links:
            if len(self._seen) >= self.max_items:
                return
            url = urljoin(response.url, href)
            if url in self._seen:
                continue
            if not self._looks_like_listing(url):
                continue
            self._seen.add(url)
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={"country_cfg": country_cfg},
            )

        next_page = (
            response.css('a[rel="next"]::attr(href)').get()
            or response.css(".pagination a.next::attr(href)").get()
        )
        if next_page and len(self._seen) < self.max_items:
            yield scrapy.Request(
                urljoin(response.url, next_page),
                callback=self.parse_index,
                meta=response.meta,
            )

    def _looks_like_listing(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        keywords = ("property", "listing", "immobil", "inmueble", "imovel", "annonce")
        return any(k in path for k in keywords) and path.count("/") >= 2

    def parse_listing(self, response):
        country_cfg = response.meta["country_cfg"]
        code = country_code_from_url(response.url) or self.country_code

        blocks = extract_json_ld(response)
        row = listing_from_json_ld(
            blocks,
            country_code=code,
            source_url=response.url,
            default_city=country_cfg.get("default_city", country_cfg["name"]),
            currency_default=country_cfg.get("currency", "EUR"),
        )
        if not row:
            return

        item = ListingItem()
        for key, value in row.items():
            if key in item.fields:
                item[key] = value
        yield item

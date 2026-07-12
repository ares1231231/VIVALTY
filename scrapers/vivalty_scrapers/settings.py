# Scrapy settings for Vivalty listing ingestion.

import os
from pathlib import Path

BOT_NAME = "vivalty_scrapers"

SPIDER_MODULES = ["vivalty_scrapers.spiders"]
NEWSPIDER_MODULE = "vivalty_scrapers.spiders"

ADDONS = {}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIVALTY_FEEDS_FILE = os.getenv(
    "VIVALTY_FEEDS_FILE",
    str(PROJECT_ROOT / "scrapers" / "feeds.yaml"),
)
VIVALTY_SCRAPER_OUTPUT = os.getenv(
    "VIVALTY_SCRAPER_OUTPUT",
    str(PROJECT_ROOT / "data" / "scraped" / "listings.json"),
)

USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "VivaltyListingBot/1.0 (+https://vivalty.com; authorized feed ingestion)",
)

ROBOTSTXT_OBEY = os.getenv("SCRAPER_OBEY_ROBOTS", "1") == "1"

CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv("SCRAPER_CONCURRENCY", "2"))
DOWNLOAD_DELAY = float(os.getenv("SCRAPER_DOWNLOAD_DELAY", "1.5"))
COOKIES_ENABLED = True

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,fr,es,pt,it;q=0.9",
}

# Optional HTTP/S proxy — set SCRAPER_PROXY=http://user:pass@host:port
_proxy = os.getenv("SCRAPER_PROXY", "").strip()
if _proxy:
    PROXY_URL = _proxy

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0

ITEM_PIPELINES = {
    "vivalty_scrapers.pipelines.JsonExportPipeline": 300,
}

FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = os.getenv("SCRAPER_LOG_LEVEL", "INFO")

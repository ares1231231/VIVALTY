"""Run Scrapy spiders and import results into the Vivalty database.

Examples:
    python manage.py scrape_listings --spider kyero --country PT --max 100
    python manage.py scrape_listings --spider kyero --all-countries --max 100
    python manage.py scrape_listings --spider json_ld --country ES --start-url https://example.com/sale

Environment (optional):
    SCRAPER_PROXY          HTTP proxy if the target blocks datacenter IPs
    SCRAPER_OBEY_ROBOTS=0  Disable robots.txt (only if you have explicit permission)
    SCRAPER_USER_AGENT     Custom user-agent string
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.properties.services.listing_import import import_listing_rows

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRAPERS_DIR = PROJECT_ROOT / "scrapers"
SCRAPED_DIR = PROJECT_ROOT / "data" / "scraped"

COUNTRY_CODES = ("PT", "ES", "FR", "GB", "IT", "CH", "AE")


class Command(BaseCommand):
    help = "Scrape authorized listing feeds with Scrapy and import into Property rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--spider",
            default="kyero",
            choices=("kyero", "json_ld"),
            help="Scrapy spider to run (default: kyero).",
        )
        parser.add_argument(
            "--country",
            default="PT",
            help="ISO country code (PT, ES, FR, GB, IT, CH, AE).",
        )
        parser.add_argument(
            "--all-countries",
            action="store_true",
            help="Run the spider once per configured country (7 markets).",
        )
        parser.add_argument(
            "--max",
            type=int,
            default=100,
            help="Max listings per country run (default: 100).",
        )
        parser.add_argument(
            "--start-url",
            default="",
            help="Optional start URL (json_ld spider only).",
        )
        parser.add_argument(
            "--scrape-only",
            action="store_true",
            help="Run Scrapy but do not import into the database.",
        )
        parser.add_argument(
            "--import-only",
            metavar="FILE",
            help="Skip scraping; import an existing JSON file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate import without writing to the database.",
        )

    def handle(self, *args, **options):
        if options["import_only"]:
            self._import_file(Path(options["import_only"]), dry_run=options["dry_run"])
            return

        countries = list(COUNTRY_CODES) if options["all_countries"] else [options["country"].upper()]

        total_created = 0
        total_updated = 0

        for code in countries:
            if code not in COUNTRY_CODES:
                raise CommandError(f"Unsupported country code: {code}")

            output = SCRAPED_DIR / f"{options['spider']}_{code.lower()}.json"
            self.stdout.write(f"Scraping {code} -> {output}")

            self._run_scrapy(
                spider=options["spider"],
                country=code,
                max_items=options["max"],
                output=output,
                start_url=options["start_url"],
            )

            if options["scrape_only"]:
                self.stdout.write(self.style.WARNING(f"Scrape-only: saved {output}"))
                continue

            if not output.is_file():
                self.stdout.write(self.style.WARNING(f"No output file for {code} (blocked or empty)."))
                continue

            with output.open(encoding="utf-8") as fh:
                rows = json.load(fh)

            if not rows:
                self.stdout.write(self.style.WARNING(f"No listings scraped for {code}."))
                continue

            created, updated = self._import_rows(rows, dry_run=options["dry_run"])
            total_created += created
            total_updated += updated
            self.stdout.write(
                self.style.SUCCESS(f"{code}: imported {created} new, {updated} updated ({len(rows)} scraped).")
            )

        if not options["scrape_only"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done — {total_created} created, {total_updated} updated across {len(countries)} market(s)."
                )
            )

    def _run_scrapy(
        self,
        *,
        spider: str,
        country: str,
        max_items: int,
        output: Path,
        start_url: str,
    ) -> None:
        SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["VIVALTY_SCRAPER_OUTPUT"] = str(output)
        env["VIVALTY_FEEDS_FILE"] = str(SCRAPERS_DIR / "feeds.yaml")
        if os.getenv("SCRAPER_OBEY_ROBOTS", "1") == "0":
            env["SCRAPER_OBEY_ROBOTS"] = "0"

        cmd = [
            sys.executable,
            "-m",
            "scrapy",
            "crawl",
            spider,
            "-a",
            f"country={country}",
            "-a",
            f"max_items={max_items}",
            "-a",
            f"feeds_file={SCRAPERS_DIR / 'feeds.yaml'}",
            "-s",
            f"VIVALTY_SCRAPER_OUTPUT={output}",
        ]
        if os.getenv("SCRAPER_OBEY_ROBOTS", "1") == "0":
            cmd.extend(["-s", "ROBOTSTXT_OBEY=0"])
        if start_url:
            cmd.extend(["-a", f"start_url={start_url}"])

        self.stdout.write(" ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd=SCRAPERS_DIR,
            env=env,
            capture_output=False,
        )
        if result.returncode != 0:
            raise CommandError(f"Scrapy exited with code {result.returncode} for {country}.")

    @transaction.atomic
    def _import_rows(self, rows: list, *, dry_run: bool) -> tuple[int, int]:
        return import_listing_rows(rows, dry_run=dry_run)

    @transaction.atomic
    def _import_file(self, path: Path, *, dry_run: bool) -> None:
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        with path.open(encoding="utf-8") as fh:
            rows = json.load(fh)
        created, updated = import_listing_rows(rows, dry_run=dry_run)
        self.stdout.write(self.style.SUCCESS(f"Imported {created} new, {updated} updated from {path}."))

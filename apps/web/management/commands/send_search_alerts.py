"""Send 'new homes' email alerts for users' saved searches.

Run on a schedule (e.g. a Railway/cron daily job):

    python manage.py send_search_alerts            # send due alerts
    python manage.py send_search_alerts --dry-run  # report only, send nothing
    python manage.py send_search_alerts --force     # ignore the frequency window

For each active saved search that is *due*, we find listings created since the
last alert (or since the search was created) that still match the saved filters,
email up to ``--limit`` of them, and advance ``last_sent_at``.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.http import QueryDict
from django.utils import timezone

from apps.web.models import SavedSearch
from apps.web.services import listing_filters
from apps.web.services.emails import send_saved_search_alert

_WINDOW = {
    SavedSearch.Frequency.DAILY: timedelta(days=1),
    SavedSearch.Frequency.WEEKLY: timedelta(days=7),
}


class Command(BaseCommand):
    help = "Email users new listings matching their saved searches."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; send nothing.")
        parser.add_argument("--force", action="store_true", help="Ignore the frequency window.")
        parser.add_argument("--limit", type=int, default=10, help="Max listings per email.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        force = opts["force"]
        limit = max(1, opts["limit"])
        now = timezone.now()

        searches = (
            SavedSearch.objects.select_related("user")
            .filter(is_active=True)
            .order_by("id")
        )

        sent = skipped = empty = 0
        for s in searches:
            window = _WINDOW.get(s.frequency, _WINDOW[SavedSearch.Frequency.DAILY])
            due = force or s.last_sent_at is None or (now - s.last_sent_at) >= window
            if not due:
                skipped += 1
                continue

            cutoff = s.last_sent_at or s.created_at
            params = QueryDict(s.query or "")
            qs = listing_filters.apply_filters(listing_filters.base_active_queryset(), params)
            qs = qs.filter(created_at__gt=cutoff).order_by("-created_at")
            new_listings = list(qs[:limit])

            if new_listings:
                if dry:
                    self.stdout.write(
                        f"[dry-run] would email {s.user.email}: {len(new_listings)} new for '{s.label}'"
                    )
                else:
                    if s.user.email:
                        send_saved_search_alert(s.user, s, new_listings)
                sent += 1
            else:
                empty += 1

            if not dry:
                s.last_sent_at = now
                s.save(update_fields=["last_sent_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. emailed={sent} no-new={empty} not-due={skipped} (dry_run={dry})"
            )
        )

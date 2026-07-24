"""Email owners whose paid featured boosts lapse within the next 2 days.

Idempotent via the ``expiry_reminder_sent`` flag, so it's safe to run on
every boot (railway-start.sh) or daily via cron.

Usage:
    python manage.py notify_expiring_boosts
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import FeaturedListingPurchase
from apps.web.services.emails import send_boost_expiring


class Command(BaseCommand):
    help = "Send renewal reminders for featured boosts expiring within 2 days."

    def handle(self, *args, **options):
        now = timezone.now()
        expiring = FeaturedListingPurchase.objects.select_related(
            "property__city", "property__country", "user"
        ).filter(
            expiry_reminder_sent=False,
            ends_at__gt=now,
            ends_at__lte=now + timedelta(days=2),
            property__is_featured=True,
        )
        sent = 0
        for purchase in expiring:
            send_boost_expiring(purchase)
            purchase.expiry_reminder_sent = True
            purchase.save(update_fields=["expiry_reminder_sent"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} boost-expiry reminder(s)."))

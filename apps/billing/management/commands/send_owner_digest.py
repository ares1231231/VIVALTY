"""Weekly performance digest for listing owners.

Schedule weekly (e.g. Railway cron: ``0 9 * * 1``). Not wired into the boot
script on purpose — running it on every deploy would spam owners.

Usage:
    python manage.py send_owner_digest
"""

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q, Sum

from apps.properties.models import Property
from apps.users.models import User
from apps.web.services.emails import send_owner_digest


class Command(BaseCommand):
    help = "Email each owner a summary of their listings' views and enquiries."

    def handle(self, *args, **options):
        platform = Property.objects.filter(status="active").aggregate(
            feat=Avg("views_count", filter=Q(is_featured=True)),
            reg=Avg("views_count", filter=Q(is_featured=False)),
        )
        # Only claim a multiplier once standard listings average >= 1 view,
        # otherwise tiny seed data produces absurd ratios. Capped at 10x.
        boost_multiplier = 0
        if platform["feat"] and platform["reg"] and platform["reg"] >= 1:
            boost_multiplier = min(10, round(platform["feat"] / platform["reg"]))
        if boost_multiplier < 2:
            boost_multiplier = 0

        owners = (
            User.objects.filter(properties__status__in=["active", "pending"])
            .annotate(
                listing_count=Count("properties", filter=Q(properties__status__in=["active", "pending"])),
                total_views=Sum("properties__views_count", filter=Q(properties__status="active")),
                total_leads=Sum("properties__leads_count", filter=Q(properties__status="active")),
            )
            .distinct()
        )
        sent = 0
        for owner in owners:
            send_owner_digest(
                owner,
                {
                    "listing_count": owner.listing_count,
                    "total_views": owner.total_views or 0,
                    "total_leads": owner.total_leads or 0,
                    "boost_multiplier": boost_multiplier,
                },
            )
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} owner digest(s)."))

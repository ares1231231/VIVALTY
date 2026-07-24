"""Unfeature listings whose paid boosts have lapsed.

Run daily (or on every boot via railway-start.sh). Editorially featured
listings — those without any purchase rows — are never touched.

Usage:
    python manage.py expire_featured
"""

from django.core.management.base import BaseCommand

from apps.billing.services.stripe_service import expire_featured_boosts


class Command(BaseCommand):
    help = "Unfeature properties whose paid featured boosts have expired."

    def handle(self, *args, **options):
        count = expire_featured_boosts()
        self.stdout.write(self.style.SUCCESS(f"Unfeatured {count} propert(ies)."))

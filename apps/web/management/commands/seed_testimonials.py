"""Seed default testimonials for the home page."""

from django.core.management.base import BaseCommand

from apps.web.models import Testimonial

DEFAULTS = [
    {
        "name": "Sophie M.",
        "location": "Bought in Lisbon",
        "quote": "Vivalty made finding our apartment in Alfama straightforward — clear photos, honest descriptions and a responsive agent.",
        "rating": 5,
        "order": 1,
    },
    {
        "name": "James & Priya K.",
        "location": "Relocated to Valencia",
        "quote": "We compared neighbourhoods using the destination guides, then booked viewings within a week. The whole process felt calm and organised.",
        "rating": 5,
        "order": 2,
    },
    {
        "name": "Ahmed R.",
        "location": "Dubai Marina",
        "quote": "As a first-time buyer in Dubai, having verified listings and WhatsApp contact made all the difference. Highly recommend.",
        "rating": 5,
        "order": 3,
    },
]


class Command(BaseCommand):
    help = "Seed default buyer testimonials (skips if any active testimonials exist)."

    def handle(self, *args, **options):
        if Testimonial.objects.filter(is_active=True).exists():
            self.stdout.write(self.style.WARNING("Active testimonials already exist — skipping."))
            return

        for row in DEFAULTS:
            Testimonial.objects.create(is_active=True, **row)

        self.stdout.write(self.style.SUCCESS(f"Created {len(DEFAULTS)} testimonials."))

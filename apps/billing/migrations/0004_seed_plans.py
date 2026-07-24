"""Seed the three launch pricing tiers. Idempotent by plan code."""

from django.db import migrations

PLANS = [
    {
        "code": "free",
        "name": "Free",
        "monthly_price": 0,
        "yearly_price": 0,
        "listing_quota": 3,
        "featured_quota": 0,
        "ai_chat_messages_per_month": 50,
        "description": "List up to 3 properties with standard placement and email lead alerts.",
    },
    {
        "code": "pro",
        "name": "Pro",
        "monthly_price": 29,
        "yearly_price": 290,
        "listing_quota": 15,
        "featured_quota": 1,
        "ai_chat_messages_per_month": 500,
        "description": "For serious owners: 15 active listings, 1 always-on featured slot, priority support.",
    },
    {
        "code": "agency",
        "name": "Agency",
        "monthly_price": 99,
        "yearly_price": 990,
        "listing_quota": 100,
        "featured_quota": 5,
        "ai_chat_messages_per_month": 2000,
        "description": "For agencies: 100 active listings, 5 featured slots, agency branding on every listing.",
    },
]


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for row in PLANS:
        Plan.objects.update_or_create(code=row["code"], defaults=row)


def unseed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(code__in=[p["code"] for p in PLANS], subscriptions__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_initial"),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]

# Generated manually for featured_until (paid-boost auto-expiry)

from django.db import migrations, models
from django.utils import timezone


def backfill_featured_until(apps, schema_editor):
    """Tag currently-paid featured listings so expire_featured can clear them."""
    Property = apps.get_model("properties", "Property")
    FeaturedListingPurchase = apps.get_model("billing", "FeaturedListingPurchase")
    now = timezone.now()
    for prop in Property.objects.filter(is_featured=True):
        active = (
            FeaturedListingPurchase.objects.filter(property_id=prop.pk, ends_at__gt=now)
            .order_by("-ends_at")
            .first()
        )
        if active:
            Property.objects.filter(pk=prop.pk).update(featured_until=active.ends_at)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0007_lead_status"),
        ("billing", "0004_seed_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="property",
            name="featured_until",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="When set, auto-expire unfeatures after this time (paid boost). "
                "Null means editorial / plan-slot featuring — never auto-expired.",
                null=True,
            ),
        ),
        migrations.RunPython(backfill_featured_until, noop_reverse),
    ]

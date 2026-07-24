# Adds idempotency flag for boost-expiry reminder emails.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_seed_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="featuredlistingpurchase",
            name="expiry_reminder_sent",
            field=models.BooleanField(
                default=False,
                help_text="Renewal reminder emailed before the boost lapsed.",
            ),
        ),
    ]

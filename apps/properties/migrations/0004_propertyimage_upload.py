"""Add ImageField uploads alongside the legacy URL field on PropertyImage.

This unlocks drag-and-drop uploads in the listing wizard while preserving
existing listings that reference externally hosted (Unsplash / Cloudinary)
URLs. Either field may be set; templates read `PropertyImage.display_url`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0003_premium_trust_upgrade"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertyimage",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="properties/%Y/%m/"),
        ),
        migrations.AlterField(
            model_name="propertyimage",
            name="url",
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]

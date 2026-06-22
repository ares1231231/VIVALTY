"""Backfill: treat existing featured/premium listings as editorially verified."""

from __future__ import annotations

from django.db import migrations


def mark_verified(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    Property.objects.filter(is_featured=True).update(is_verified=True)
    Property.objects.filter(is_premium=True).update(is_verified=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0005_property_is_verified"),
    ]

    operations = [
        migrations.RunPython(mark_verified, noop),
    ]

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Property
from .services.scoring import upsert_metric


@receiver(post_save, sender=Property)
def refresh_metric(sender, instance: Property, created: bool, **_kwargs):
    """Keep InvestmentMetric in sync with the listing it scores."""
    upsert_metric(instance)

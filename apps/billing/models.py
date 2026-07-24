"""Monetization models — schema only, payment provider plug-in left as TODO.

Three concepts:
    - Plan         : a pricing tier (Free / Pro / Agency / Enterprise)
    - Subscription : a user's active subscription
    - FeaturedListingPurchase : a one-off boost for a property
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Plan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    monthly_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    yearly_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="EUR")

    listing_quota = models.PositiveIntegerField(default=3, help_text="Max active listings.")
    featured_quota = models.PositiveIntegerField(default=0)
    ai_chat_messages_per_month = models.PositiveIntegerField(default=50)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    current_period_end = models.DateTimeField(null=True, blank=True)
    external_ref = models.CharField(max_length=200, blank=True, help_text="e.g. Stripe sub id")
    created_at = models.DateTimeField(auto_now_add=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class FeaturedListingPurchase(models.Model):
    property = models.ForeignKey(
        "properties.Property", on_delete=models.CASCADE, related_name="feature_purchases"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="feature_purchases"
    )
    duration_days = models.PositiveSmallIntegerField(default=14)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    external_ref = models.CharField(max_length=200, blank=True)
    expiry_reminder_sent = models.BooleanField(
        default=False, help_text="Renewal reminder emailed before the boost lapsed."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

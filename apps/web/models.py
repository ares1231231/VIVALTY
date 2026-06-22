"""Website-only domain models.

These exist for the marketing/conversion surface (lead capture, investor
inquiry funnel) and are intentionally separate from `apps.properties.Lead`
which is scoped to a single listing.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class SavedSearch(models.Model):
    """A user's saved marketplace search, used to send 'new homes' email alerts.

    ``query`` stores the marketplace querystring (without paging) so the alert
    command can replay the exact filters the user saved.
    """

    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    label = models.CharField(max_length=160)
    query = models.CharField(
        max_length=500,
        blank=True,
        help_text="URL-encoded marketplace filters, e.g. 'country=PT&type=apartment&price_max=300000'.",
    )
    frequency = models.CharField(
        max_length=10, choices=Frequency.choices, default=Frequency.DAILY
    )
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Saved searches"
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.user_id})"


class Testimonial(models.Model):
    """A short buyer/owner testimonial shown on marketing surfaces (home page)."""

    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True, help_text="e.g. 'Bought in Lisbon'")
    quote = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5, help_text="1–5 stars")
    avatar_url = models.URLField(max_length=600, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.rating}★)"


class InvestorProfile(models.TextChoices):
    INDIVIDUAL = "individual", "Individual investor"
    FAMILY_OFFICE = "family_office", "Family office"
    FUND = "fund", "Fund / institution"
    DEVELOPER = "developer", "Developer / broker"


class InvestorInquiry(models.Model):
    """High-intent investor lead, not tied to a single property.

    Captured from the home hero, methodology page, premium-analytics paywall
    and the investor-relations CTA in the footer. We persist the originating
    page so growth can A/B-test copy & funnels independently.
    """

    name = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=32, blank=True)

    profile = models.CharField(
        max_length=32,
        choices=InvestorProfile.choices,
        default=InvestorProfile.INDIVIDUAL,
    )
    budget_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    budget_currency = models.CharField(max_length=3, default="EUR")
    markets_of_interest = models.CharField(
        max_length=500,
        blank=True,
        help_text="Free text: countries or cities the investor cares about.",
    )
    message = models.TextField(blank=True)

    source_page = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Investor inquiries"

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> ({self.profile})"

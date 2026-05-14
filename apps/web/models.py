"""Website-only domain models.

These exist for the marketing/conversion surface (lead capture, investor
inquiry funnel) and are intentionally separate from `apps.properties.Lead`
which is scoped to a single listing.
"""

from __future__ import annotations

from django.db import models


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

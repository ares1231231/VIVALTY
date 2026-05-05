"""Geographic taxonomy.

Country/City carry market-level baselines used by the investment scoring
engine. These values are intentionally editable in admin so the platform can
absorb new market data without code changes.
"""

from __future__ import annotations

from django.db import models


class TrendChoices(models.TextChoices):
    GROWTH = "growth", "Growth"
    STABLE = "stable", "Stable"
    DECLINING = "declining", "Declining"


class RiskChoices(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class DemandChoices(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True, db_index=True, help_text="ISO-3166-1 alpha-2")
    name = models.CharField(max_length=100, unique=True)
    currency = models.CharField(max_length=3, default="EUR", help_text="ISO-4217")
    flag_emoji = models.CharField(max_length=8, blank=True)

    # Market baselines (used as fallback when a city / property lacks data)
    base_roi_min = models.DecimalField(max_digits=5, decimal_places=2, default=3.0)
    base_roi_max = models.DecimalField(max_digits=5, decimal_places=2, default=6.0)
    base_rental_yield = models.DecimalField(max_digits=5, decimal_places=2, default=4.0)
    base_demand = models.CharField(max_length=10, choices=DemandChoices.choices, default=DemandChoices.MEDIUM)
    base_trend = models.CharField(max_length=10, choices=TrendChoices.choices, default=TrendChoices.STABLE)
    base_risk = models.CharField(max_length=10, choices=RiskChoices.choices, default=RiskChoices.MEDIUM)

    summary = models.TextField(blank=True, help_text="Short market overview shown to investors and to the AI.")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Countries"

    def __str__(self) -> str:
        return f"{self.flag_emoji} {self.name}".strip()


class City(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=120, db_index=True)
    slug = models.SlugField(max_length=140, db_index=True)

    population = models.PositiveIntegerField(null=True, blank=True)
    avg_price_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    avg_rental_yield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    demand = models.CharField(max_length=10, choices=DemandChoices.choices, null=True, blank=True)
    trend = models.CharField(max_length=10, choices=TrendChoices.choices, null=True, blank=True)
    risk = models.CharField(max_length=10, choices=RiskChoices.choices, null=True, blank=True)
    investment_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="0-100")

    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["country__name", "name"]
        unique_together = ("country", "slug")
        indexes = [
            models.Index(fields=["country", "name"]),
            models.Index(fields=["investment_score"]),
        ]
        verbose_name_plural = "Cities"

    def __str__(self) -> str:
        return f"{self.name}, {self.country.code}"

"""Listing domain.

Schema is normalized: Property → City → Country, with denormalized country
ref kept for fast filtering, plus a 1-to-1 InvestmentMetric for AI-friendly
scoring data and an indexed `slug` for SEO URLs.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.geo.models import City, Country, DemandChoices, RiskChoices, TrendChoices


class PropertyType(models.TextChoices):
    APARTMENT = "apartment", "Apartment"
    VILLA = "villa", "Villa"
    HOUSE = "house", "House"
    COMMERCIAL = "commercial", "Commercial"
    LAND = "land", "Land"
    OFFICE = "office", "Office"
    RETAIL = "retail", "Retail"


class Status(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    SOLD = "sold", "Sold"
    RENTED = "rented", "Rented"
    PENDING = "pending", "Pending review"
    ARCHIVED = "archived", "Archived"


class InvestmentTag(models.Model):
    """Free-form tags such as 'High ROI', 'Luxury', 'Emerging market'."""

    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    color = models.CharField(max_length=24, default="emerald")

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Property(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties"
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, db_index=True, blank=True)
    description = models.TextField(blank=True)

    property_type = models.CharField(
        max_length=20, choices=PropertyType.choices, default=PropertyType.APARTMENT, db_index=True
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    price = models.DecimalField(max_digits=14, decimal_places=2, db_index=True)
    currency = models.CharField(max_length=3, default="EUR")

    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="properties")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="properties")
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    area_sqm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)

    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)

    tags = models.ManyToManyField(InvestmentTag, blank=True, related_name="properties")

    is_featured = models.BooleanField(default=False, db_index=True)
    is_premium = models.BooleanField(default=False, db_index=True)

    views_count = models.PositiveIntegerField(default=0)
    leads_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        indexes = [
            models.Index(fields=["country", "city", "status"]),
            models.Index(fields=["price"]),
            models.Index(fields=["property_type", "status"]),
        ]
        verbose_name_plural = "Properties"

    def __str__(self) -> str:
        return f"{self.title} ({self.city.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.title}-{self.city.name}")[:230]
            self.slug = f"{base}-{self.pk or ''}".strip("-") or base
        return super().save(*args, **kwargs)

    @property
    def primary_image_url(self) -> str | None:
        first = self.images.order_by("position").first()
        return first.url if first else None


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=1000)
    caption = models.CharField(max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"Image for {self.property_id}"


class InvestmentMetric(models.Model):
    """Per-property scoring snapshot.

    Computed by `apps.properties.services.scoring.compute_metric` and refreshed
    on save / via management command. Stored (rather than computed-on-read) so
    listing queries stay cheap and the AI advisor can RAG over them.
    """

    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name="metric"
    )

    estimated_roi_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    estimated_roi_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    rental_yield = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))

    demand = models.CharField(max_length=10, choices=DemandChoices.choices, default=DemandChoices.MEDIUM)
    market_trend = models.CharField(max_length=10, choices=TrendChoices.choices, default=TrendChoices.STABLE)
    risk_level = models.CharField(max_length=10, choices=RiskChoices.choices, default=RiskChoices.MEDIUM)

    investment_score = models.PositiveSmallIntegerField(default=0, db_index=True)

    is_estimated = models.BooleanField(
        default=True,
        help_text="True when values were derived from market baselines rather than verified data.",
    )
    notes = models.TextField(blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-investment_score"]

    def __str__(self) -> str:
        return f"Metric<{self.property_id}> score={self.investment_score}"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "property")
        ordering = ["-created_at"]


class Lead(models.Model):
    """Contact-form submission for a property — feeds the lead-gen funnel."""

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="leads")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_sent",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

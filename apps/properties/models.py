"""Listing domain.

Schema is normalized: Property → City → Country, with denormalized country
ref kept for fast filtering, plus a 1-to-1 InvestmentMetric for AI-friendly
scoring data and an indexed `slug` for SEO URLs.
"""

from __future__ import annotations

import builtins
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

    listing_agency = models.CharField(
        max_length=200,
        blank=True,
        help_text="Brokerage or developer marketing this listing.",
    )
    listing_ref = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Internal or MLS-style reference shown to investors.",
    )

    tags = models.ManyToManyField(InvestmentTag, blank=True, related_name="properties")

    is_featured = models.BooleanField(default=False, db_index=True)
    is_premium = models.BooleanField(default=False, db_index=True)
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Listing details checked by Vivalty's editorial desk.",
    )

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
        return first.display_url if first else None


class PropertyImage(models.Model):
    """Image for a property.

    Two ways to populate the visual:
    - ``image``  → file upload (drag-and-drop in the listing wizard, served
      from MEDIA_ROOT)
    - ``url``    → externally hosted URL (legacy, paste-URL fallback)

    Use :pyattr:`display_url` to read whichever is available without caring.
    """

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="properties/%Y/%m/", null=True, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    caption = models.CharField(max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"Image for {self.property_id}"

    # ``property`` is a foreign-key field on this model, which shadows the
    # builtin inside the class body. Reach for the builtin via the module.
    @builtins.property
    def display_url(self) -> str | None:
        if self.image:
            try:
                return self.image.url
            except ValueError:
                return None
        return self.url or None


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
    score_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Explainability payload: factor scores, strengths, risks.",
    )
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


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    CLOSED = "closed", "Closed"


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
    status = models.CharField(
        max_length=12, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

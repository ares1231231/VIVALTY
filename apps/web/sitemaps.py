"""XML sitemap definitions for public SEO pages."""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.properties.models import Property, Status


class StaticViewSitemap(Sitemap):
    """Marketing and discovery pages."""

    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "web:home",
            "web:marketplace",
            "web:markets",
            "web:methodology",
            "web:simulator",
            "web:compare",
            "web:listing_start",
            "web:investor_inquiry",
        ]

    def location(self, item):
        return reverse(item)


class PropertySitemap(Sitemap):
    """Active property detail pages."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Property.objects.filter(status=Status.ACTIVE).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("web:property_detail", kwargs={"pk": obj.pk})

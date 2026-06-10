"""XML sitemap definitions for public SEO pages."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.properties.models import Property, Status


class _SiteUrlSitemap(Sitemap):
    """Build absolute URLs from SITE_URL so production always uses the apex domain."""

    changefreq = "weekly"

    def get_domain(self, site=None):
        host = urlparse(settings.SITE_URL).hostname
        return host or "vivalty.com"

    def get_protocol(self, protocol=None):
        scheme = urlparse(settings.SITE_URL).scheme
        return scheme or "https"


class StaticViewSitemap(_SiteUrlSitemap):
    """Marketing and discovery pages."""

    priority = 0.8

    def items(self):
        return [
            "web:home",
            "web:marketplace",
            "web:markets",
            "web:methodology",
            "web:simulator",
            "web:compare",
            "web:become_owner",
            "web:privacy",
            "web:terms",
            "web:cookies",
            "web:legal_notice",
            "web:contact",
        ]

    def location(self, item):
        return reverse(item)


class PropertySitemap(_SiteUrlSitemap):
    """Active property detail pages."""

    priority = 0.7

    def items(self):
        return Property.objects.filter(status=Status.ACTIVE).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("web:property_detail", kwargs={"pk": obj.pk})

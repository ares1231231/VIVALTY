"""XML sitemap definitions for public SEO pages."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.properties.models import Property, Status
from apps.web.services import city_guides as _city_guides
from apps.web.services import destinations as _destinations


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
        pages = [
            "web:home",
            "web:marketplace",
            "web:destinations",
            "web:quiz",
            "web:price_explorer",
            "web:become_owner",
            "web:privacy",
            "web:terms",
            "web:cookies",
            "web:legal_notice",
            "web:contact",
        ]
        if settings.SHOW_INVESTMENT_FEATURES:
            pages[5:5] = [
                "web:markets",
                "web:methodology",
                "web:simulator",
                "web:compare",
            ]
        return pages

    def location(self, item):
        return reverse(item)


class DestinationSitemap(_SiteUrlSitemap):
    """Per-country destination guide pages."""

    priority = 0.8

    def items(self):
        return _destinations.guide_slugs()

    def location(self, slug):
        return reverse("web:destination_detail", kwargs={"slug": slug})


class CityGuideSitemap(_SiteUrlSitemap):
    """City-level destination guides (Living in Lisbon, etc.)."""

    priority = 0.75

    def items(self):
        return _city_guides.all_city_guide_keys()

    def location(self, item):
        country_code, city_slug = item
        guide = _destinations.guide_by_code(country_code)
        if guide is None:
            return "/"
        return reverse(
            "web:city_destination",
            kwargs={"country_slug": guide.slug, "city_slug": city_slug},
        )


class PropertySitemap(_SiteUrlSitemap):
    """Active property detail pages."""

    priority = 0.7

    def items(self):
        return Property.objects.filter(status=Status.ACTIVE).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("web:property_detail", kwargs={"pk": obj.pk})

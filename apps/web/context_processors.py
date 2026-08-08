"""Template context for site-wide SEO defaults."""

from __future__ import annotations

import json

from django.conf import settings

# Fallback copy when a page does not override `seo_head`.
_PAGE_SEO: dict[str, tuple[str, str]] = {
    "home": (
        "Vivalty — International real estate, beautifully curated",
        "Discover apartments, villas and houses across France, Portugal, Spain, Italy, Switzerland, "
        "the UAE and the UK. Buy or rent with verified listings and local destination guides.",
    ),
    "marketplace": (
        "Property marketplace · Vivalty",
        "Browse international property listings. Filter by country, type and budget across "
        "7 destinations with verified details, photos and direct agency contact.",
    ),
    "markets": (
        "Destinations · Vivalty",
        "Explore Vivalty's 7 international property destinations — from Lisbon and Paris to "
        "Dubai and London.",
    ),
    "destinations": (
        "Destination guides · Buy property abroad · Vivalty",
        "Practical guides to buying a home in Portugal, Spain, France, Italy, the UK, the UAE "
        "and Switzerland — lifestyle, neighbourhoods, the buying process and FAQs.",
    ),
    "quiz": (
        "Where should you buy? · Dream-home quiz · Vivalty",
        "Take our 1-minute quiz to discover your perfect international destination — "
        "and see real homes that match your lifestyle and budget.",
    ),
    "methodology": (
        "About our listings · Vivalty",
        "How Vivalty curates, verifies and presents international property listings.",
    ),
    "simulator": (
        "Property tools · Vivalty",
        "Vivalty property tools and resources for international buyers.",
    ),
    "simulator_property": (
        "Property tools · Vivalty",
        "Vivalty property tools and resources for international buyers.",
    ),
    "compare": (
        "Compare properties · Vivalty",
        "Side-by-side comparison of international property listings.",
    ),
    "sell": (
        "Sell your property · Vivalty",
        "List your home free on Vivalty. AI-assisted listing, zero commission to publish, "
        "and direct enquiries from international buyers.",
    ),
    "become_owner": (
        "List your property on Vivalty · Vivalty",
        "Reach international buyers and renters. List residential or commercial property with "
        "professional presentation and enquiry capture.",
    ),
    "property_detail": (
        "Property listing · Vivalty",
        "International property listing on Vivalty with full details, photos and location guides.",
    ),
    "login": (
        "Sign in · Vivalty",
        "Sign in to your Vivalty account.",
    ),
    "register": (
        "Create account · Vivalty",
        "Create a free Vivalty account to save favorites and contact sellers.",
    ),
    "dashboard": (
        "Your dashboard · Vivalty",
        "Your Vivalty dashboard — saved properties and listing tools.",
    ),
    "chat": (
        "AI property assistant · Vivalty",
        "Chat with the Vivalty assistant about destinations and listings.",
    ),
    "privacy": (
        "Privacy Policy · Vivalty",
        "How Vivalty collects, uses and protects your personal data when you browse listings, "
        "create an account or contact our team.",
    ),
    "terms": (
        "Terms of Service · Vivalty",
        "Terms governing use of the Vivalty property marketplace and services.",
    ),
    "cookies": (
        "Cookie Policy · Vivalty",
        "How Vivalty uses cookies and similar technologies on vivalty.com.",
    ),
    "legal_notice": (
        "Legal Notice · Vivalty",
        "Publisher information, business identity and regulatory disclosures for Vivalty.",
    ),
    "contact": (
        "Contact · Vivalty",
        "Contact the Vivalty team for buyer enquiries, listing support and general questions.",
    ),
    "price_explorer": (
        "What does your budget buy? · Price explorer · Vivalty",
        "Compare what €150k to €1M buys across Portugal, Spain, France, Italy, the UK, "
        "the UAE and Switzerland — interactive, curiosity-driven, no financial advice.",
    ),
    "city_destination": (
        "City guide · Vivalty",
        "Living and buying a home abroad — neighbourhoods, lifestyle and practical tips.",
    ),
    "destination_detail": (
        "Buy property abroad · Destination guide · Vivalty",
        "Practical buyer's guides for international property — lifestyle, neighbourhoods and next steps.",
    ),
    "agencies": (
        "Vivalty for agencies — reach international buyers",
        "List your portfolio on Vivalty and put it in front of international buyers across "
        "7 countries. Free to start, lead inbox included, featured placement available.",
    ),
    "pricing": (
        "Pricing — sell faster on Vivalty",
        "Choose Free, Pro or Agency plans on Vivalty. Publish listings, unlock featured "
        "placement and reach international buyers with transparent pricing.",
    ),
    "property_story": (
        "Property story · Vivalty",
        "Vertical property slideshow — share on TikTok, Reels or WhatsApp.",
    ),
    "marketplace_country": (
        "Homes for sale abroad · Vivalty",
        "Browse verified international property listings by country on Vivalty.",
    ),
}

_DEFAULT_TITLE = "Vivalty — International real estate marketplace"
_DEFAULT_DESCRIPTION = (
    "Discover apartments, villas and homes for sale or rent across France, the UK, Spain, "
    "Switzerland, Italy, the UAE and Portugal."
)


def seo(request):
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    if not site_url:
        site_url = f"{request.scheme}://{request.get_host()}"

    url_name = getattr(getattr(request, "resolver_match", None), "url_name", None) or ""
    page_title, page_description = _PAGE_SEO.get(url_name, (_DEFAULT_TITLE, _DEFAULT_DESCRIPTION))

    # Canonical = path only (no query string) to reduce duplicate-index risk from filters.
    canonical_url = f"{site_url}{request.path}"
    og_image = f"{site_url}/static/img/og-image.png"

    return {
        "SITE_URL": site_url,
        "SHOW_INVESTMENT_FEATURES": settings.SHOW_INVESTMENT_FEATURES,
        "SEO_PAGE_TITLE": page_title,
        "SEO_PAGE_DESCRIPTION": page_description,
        "SEO_CANONICAL_URL": canonical_url,
        "SEO_OG_IMAGE": og_image,
        "SEO_DEFAULT_DESCRIPTION": _DEFAULT_DESCRIPTION,
    }


def recently_viewed(request):
    """Expose the user's recently-viewed listings (from the session) site-wide."""
    try:
        ids = request.session.get("recent_views", [])
    except Exception:
        ids = []
    if not ids:
        return {"RECENTLY_VIEWED": []}

    from apps.properties.models import Property, Status

    props = (
        Property.objects.filter(id__in=ids[:12], status=Status.ACTIVE)
        .select_related("country", "city", "metric")
        .prefetch_related("images")
    )
    by_id = {p.id: p for p in props}
    ordered = [by_id[i] for i in ids if i in by_id]
    return {"RECENTLY_VIEWED": ordered[:8]}


def company(request):
    """Business identity shown on legal pages and the site footer."""
    return {
        "COMPANY_LEGAL_NAME": settings.COMPANY_LEGAL_NAME,
        "COMPANY_REGISTERED_ADDRESS": settings.COMPANY_REGISTERED_ADDRESS,
        "COMPANY_SUPPORT_EMAIL": settings.COMPANY_SUPPORT_EMAIL,
        "COMPANY_INVESTOR_EMAIL": settings.COMPANY_INVESTOR_EMAIL,
        "COMPANY_EIN": settings.COMPANY_EIN,
        "COMPANY_VAT_NUMBER": settings.COMPANY_VAT_NUMBER,
        "COMPANY_PHONE": settings.COMPANY_PHONE,
        "COMPANY_STATE_OF_FORMATION": settings.COMPANY_STATE_OF_FORMATION,
        "COMPANY_FILING_ID": settings.COMPANY_FILING_ID,
        "COMPANY_WHATSAPP": settings.COMPANY_WHATSAPP,
    }


def i18n_ui(request):
    """Expose supported languages and the active code for the language switcher."""
    from apps.web.i18n import SUPPORTED_LANGUAGES, active_language

    lang = active_language(request)
    return {
        "UI_LANGUAGES": SUPPORTED_LANGUAGES,
        "UI_LANGUAGE": lang,
        "UI_RTL": lang == "ar",
    }


def analytics(request):
    """GA4 / Google Ads IDs and pending conversion events (overridable per view)."""
    ga4 = getattr(settings, "GA4_MEASUREMENT_ID", "")
    ads = getattr(settings, "GOOGLE_ADS_ID", "")
    cfg = {"ga4Id": ga4, "adsId": ads, "pending": []}
    return {
        "GA4_MEASUREMENT_ID": ga4,
        "GOOGLE_ADS_ID": ads,
        "ANALYTICS_CONFIG_JSON": json.dumps(cfg),
    }

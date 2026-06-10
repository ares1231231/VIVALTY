"""Template context for site-wide SEO defaults."""

from __future__ import annotations

from django.conf import settings

# Fallback copy when a page does not override `seo_head`.
_PAGE_SEO: dict[str, tuple[str, str]] = {
    "home": (
        "Vivalty — High-performing international real estate, with confidence",
        "Discover AI-scored property across France, Portugal, Spain, Italy, Switzerland, UAE and the UK. "
        "Buy or rent with transparent investment scores, yield data and an embedded AI advisor.",
    ),
    "marketplace": (
        "Property marketplace · Vivalty",
        "Browse AI-scored international property listings. Filter by country, type and budget across "
        "7 vetted markets with investment scores, rental yields and market intelligence.",
    ),
    "markets": (
        "Global real estate markets · Vivalty",
        "Compare country baselines, rental-yield benchmarks and top-scored cities across Vivalty's "
        "7 international property markets.",
    ),
    "methodology": (
        "How our AI investment score works · Vivalty",
        "Transparent methodology behind Vivalty's 0–100 property score: yield, demand, risk, "
        "location and data sources explained.",
    ),
    "simulator": (
        "Investment simulator · Vivalty",
        "Underwrite any international property in seconds. Model gross yield, ROI, cash flow and "
        "multi-year projections with country-specific assumptions.",
    ),
    "simulator_property": (
        "Property investment simulator · Vivalty",
        "Run a full investment simulation on a Vivalty listing with editable price, yield and "
        "holding assumptions.",
    ),
    "compare": (
        "Compare property investments · Vivalty",
        "Side-by-side comparison of international listings — price, AI score, yield, ROI and "
        "key metrics in one view.",
    ),
    "become_owner": (
        "List your property on Vivalty · Vivalty",
        "Reach qualified international investors. List residential or commercial property with "
        "AI scoring, professional presentation and lead capture.",
    ),
    "property_detail": (
        "Property listing · Vivalty",
        "International property listing on Vivalty with AI investment score, yield analysis and "
        "market context.",
    ),
    "login": (
        "Sign in · Vivalty",
        "Sign in to your Vivalty investor account.",
    ),
    "register": (
        "Create account · Vivalty",
        "Create a free Vivalty account to save favorites, run simulations and contact sellers.",
    ),
    "dashboard": (
        "Investor dashboard · Vivalty",
        "Your Vivalty dashboard — saved properties, leads and listing tools.",
    ),
    "chat": (
        "AI investment advisor · Vivalty",
        "Chat with the Vivalty AI advisor — grounded in live listing and market data.",
    ),
    "privacy": (
        "Privacy Policy · Vivalty",
        "How Vivalty collects, uses and protects your personal data when you browse listings, "
        "create an account or contact our investor desk.",
    ),
    "terms": (
        "Terms of Service · Vivalty",
        "Terms governing use of the Vivalty property marketplace, research tools and AI advisor.",
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
        "Contact the Vivalty team for investor enquiries, listing support and general questions.",
    ),
}

_DEFAULT_TITLE = "Vivalty — AI-powered global real estate investing"
_DEFAULT_DESCRIPTION = (
    "Discover, analyse and invest in international real estate across France, UK, Spain, "
    "Switzerland, Italy, UAE and Portugal — guided by an embedded AI investment advisor."
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
        "SEO_PAGE_TITLE": page_title,
        "SEO_PAGE_DESCRIPTION": page_description,
        "SEO_CANONICAL_URL": canonical_url,
        "SEO_OG_IMAGE": og_image,
        "SEO_DEFAULT_DESCRIPTION": _DEFAULT_DESCRIPTION,
    }


def company(request):
    """Business identity shown on legal pages and the site footer."""
    return {
        "COMPANY_LEGAL_NAME": settings.COMPANY_LEGAL_NAME,
        "COMPANY_REGISTERED_ADDRESS": settings.COMPANY_REGISTERED_ADDRESS,
        "COMPANY_SUPPORT_EMAIL": settings.COMPANY_SUPPORT_EMAIL,
        "COMPANY_INVESTOR_EMAIL": settings.COMPANY_INVESTOR_EMAIL,
        "COMPANY_VAT_NUMBER": settings.COMPANY_VAT_NUMBER,
    }

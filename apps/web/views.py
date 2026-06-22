"""Server-rendered website views.

Thin handlers — every piece of business logic lives in the service layer
(`apps/properties/services/scoring.py`, `apps/properties/services/simulator.py`,
`apps/ai_advisor/services/*`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Iterator

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Avg, Count, F, Max, Min, Q
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST, require_http_methods
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger("vivalty.web")

from apps.ai_advisor.models import AIConversationSession, ChatMessage, Role as ChatRole
from apps.ai_advisor.services.advisor import generate, stream as advisor_stream
from apps.geo.models import City, Country
from apps.properties.models import Favorite, Property, PropertyType, Status
from apps.properties.services.scoring import FACTOR_WEIGHTS
from apps.properties.services.simulator import (
    COUNTRY_ASSUMPTIONS,
    SimulatorInputs,
    simulate,
    simulate_for_property,
)
from apps.users.models import Role, User
from apps.web.services import geocoding, listing_ai, listing_wizard
from apps.web.services.emails import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)
from .forms import (
    BecomeOwnerForm,
    EmailLoginForm,
    ForgotPasswordForm,
    InvestorInquiryForm,
    LeadForm,
    ListingLocationForm,
    ListingPriceForm,
    ListingSpecsForm,
    ListingTypeForm,
    PropertyEditForm,
    PropertyForm,
    RegisterForm,
    SetNewPasswordForm,
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _safe_decimal(raw: str | None, default: Decimal | None = None) -> Decimal | None:
    if raw in (None, ""):
        return default
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return default


def _safe_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _safe_float(raw: str | None, default: float) -> float:
    try:
        return float(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        return default


# ─── Infrastructure ─────────────────────────────────────────────────────────

def healthz(request: HttpRequest) -> HttpResponse:
    """Cheap, dependency-free health probe for Railway / load balancers.

    Intentionally returns plain text 200 with no DB queries, no template
    rendering, no SSL redirect — so the platform's internal HTTP probe can
    succeed even when the app would otherwise force HTTPS on user traffic.
    """
    return HttpResponse("ok", content_type="text/plain")


def robots_txt(request: HttpRequest) -> HttpResponse:
    """Crawler rules and sitemap pointer for search engines."""
    site = settings.SITE_URL.rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /auth/",
        "Disallow: /htmx/",
        "Disallow: /api/",
        "Disallow: /list/",
        "Allow: /list/become-owner/",
        "Disallow: /chat/",
    ]
    if not settings.SHOW_INVESTMENT_FEATURES:
        lines += [
            "Disallow: /ai-invest/",
            "Disallow: /methodology/",
            "Disallow: /compare/",
            "Disallow: /markets/",
        ]
    lines += ["", f"Sitemap: {site}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


# ─── Public pages ───────────────────────────────────────────────────────────

def home(request: HttpRequest) -> HttpResponse:
    featured_order = (
        ("-metric__investment_score",)
        if settings.SHOW_INVESTMENT_FEATURES
        else ("-is_featured", "-created_at")
    )
    featured = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images", "tags")
        .filter(status="active", is_featured=True)
        .order_by(*featured_order)[:6]
    )
    if not featured.exists():
        featured = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images", "tags")
            .filter(status="active")
            .order_by(*featured_order)[:6]
        )

    # Hero gallery — pick the highest-scored listing per country (max 3)
    # so the floating mosaic feels diverse and product-led.
    seen_countries: set[str] = set()
    hero_gallery: list[Property] = []
    hero_order = (
        ("-metric__investment_score", "-is_featured")
        if settings.SHOW_INVESTMENT_FEATURES
        else ("-is_featured", "-created_at")
    )
    for prop in (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images")
        .filter(status="active")
        .order_by(*hero_order)
    ):
        if prop.country.code in seen_countries:
            continue
        if not prop.primary_image_url:
            continue
        hero_gallery.append(prop)
        seen_countries.add(prop.country.code)
        if len(hero_gallery) >= 3:
            break

    countries = (
        Country.objects.annotate(
            cities_count=Count("cities"),
            avg_score=Avg("cities__investment_score"),
        )
        .order_by("name")
    )

    # Hero coverflow order — matches editorial mockup (UAE centered).
    _hero_country_order = ("PT", "IT", "FR", "AE", "ES", "CH", "GB")
    _by_code = {c.code: c for c in countries}
    hero_countries = [_by_code[code] for code in _hero_country_order if code in _by_code]
    if len(hero_countries) < 7:
        seen = {c.code for c in hero_countries}
        hero_countries.extend(c for c in countries if c.code not in seen)
        hero_countries = hero_countries[:7]

    # Cities grouped by country code — JSON-serialised for the hero search bar
    # so clicking a country card can repopulate the city dropdown client-side.
    cities_by_country: dict[str, list[dict[str, str]]] = {}
    for city in City.objects.select_related("country").order_by("country__name", "name"):
        cities_by_country.setdefault(city.country.code, []).append(
            {"slug": city.slug, "name": city.name}
        )

    # Aggregate platform stats — surfaced in the institutional trust strip.
    agg = Property.objects.filter(status="active").aggregate(
        total=Count("id"),
        avg_score=Avg("metric__investment_score"),
        max_yield=Max("metric__rental_yield"),
    )
    stats = {
        "total_listings": agg["total"] or 0,
        "avg_score": int(agg["avg_score"] or 0),
        "max_yield": float(agg["max_yield"] or 0),
        "countries": Country.objects.count(),
        "cities": City.objects.count(),
    }

    investor_form = InvestorInquiryForm()

    # Lite interactive simulator (home page) — seeded with a realistic Portugal
    # scenario so the widget shows live numbers before any slider interaction.
    quick_sim = None
    if settings.SHOW_INVESTMENT_FEATURES:
        quick_sim = simulate(
            SimulatorInputs(
                price=350_000.0,
                currency="EUR",
                country_code="PT",
                rental_yield_pct=6.0,
                down_payment_pct=30.0,
                mortgage_years=25,
                horizon_years=10,
            )
        )

    # Favorited property ids for the current user, so home cards can show the
    # correct heart state without an extra query per card.
    favorite_ids: set[int] = set()
    if request.user.is_authenticated:
        favorite_ids = set(
            Favorite.objects.filter(user=request.user).values_list("property_id", flat=True)
        )

    from apps.web.models import Testimonial
    from apps.web.seo_helpers import site_json_ld

    try:
        testimonials = list(
            Testimonial.objects.filter(is_active=True).order_by("order", "-created_at")[:6]
        )
    except Exception:
        testimonials = []
    if not testimonials:
        testimonials = _default_testimonials()

    return render(
        request,
        "web/home.html",
        {
            "featured": featured,
            "hero_gallery": hero_gallery,
            "countries": countries,
            "hero_countries": hero_countries,
            "cities_by_country": cities_by_country,
            "stats": stats,
            "investor_form": investor_form,
            "quick_sim": quick_sim,
            "quick_sim_country": "PT",
            "favorite_ids": favorite_ids,
            "site_json_ld": site_json_ld(),
            "testimonials": testimonials,
        },
    )


def _default_testimonials():
    """Fallback testimonials when none are configured in admin."""
    from apps.web.models import Testimonial

    return [
        Testimonial(
            name="Sophie M.",
            location="Bought in Lisbon",
            quote="Vivalty made finding our apartment in Alfama straightforward — clear photos, honest descriptions and a responsive agent.",
            rating=5,
        ),
        Testimonial(
            name="James & Priya K.",
            location="Relocated to Valencia",
            quote="We compared neighbourhoods using the destination guides, then booked viewings within a week. The whole process felt calm and organised.",
            rating=5,
        ),
        Testimonial(
            name="Ahmed R.",
            location="Dubai Marina",
            quote="As a first-time buyer in Dubai, having verified listings and WhatsApp contact made all the difference. Highly recommend.",
            rating=5,
        ),
    ]


def marketplace(request: HttpRequest) -> HttpResponse:
    from apps.web.services import listing_filters

    p = request.GET
    qs = listing_filters.apply_filters(listing_filters.base_active_queryset(), p)

    ordering = p.get("ordering") or "-is_featured,-created_at"
    if p.get("best_match") == "1":
        ordering = "-metric__investment_score,-is_featured,-created_at"
    qs = qs.order_by(*listing_filters.resolve_ordering(p))

    try:
        page = max(1, int(p.get("page", 1)))
    except ValueError:
        page = 1
    page_size = 24
    total = qs.count()
    items = list(qs[(page - 1) * page_size : page * page_size])

    countries = Country.objects.order_by("name")

    CITY_COORDS: dict[str, tuple[float, float]] = {
        "paris": (48.85, 2.35), "lyon": (45.75, 4.83), "marseille": (43.30, 5.37),
        "nice": (43.71, 7.26), "bordeaux": (44.84, -0.58), "toulouse": (43.60, 1.44),
        "london": (51.51, -0.13), "manchester": (53.48, -2.24), "birmingham": (52.48, -1.90),
        "edinburgh": (55.95, -3.19), "bristol": (51.45, -2.59),
        "madrid": (40.42, -3.70), "barcelona": (41.39, 2.15), "valencia": (39.47, -0.38),
        "seville": (37.38, -5.99), "malaga": (36.72, -4.42), "marbella": (36.51, -4.88),
        "zurich": (47.38, 8.54), "geneva": (46.20, 6.14), "basel": (47.56, 7.59),
        "lausanne": (46.52, 6.63),
        "rome": (41.90, 12.50), "milan": (45.47, 9.19), "florence": (43.77, 11.26),
        "venice": (45.44, 12.33), "naples": (40.85, 14.27),
        "dubai marina": (25.08, 55.14), "business bay": (25.19, 55.27),
        "jumeirah village circle": (25.06, 55.21), "abu dhabi": (24.47, 54.37),
        "lisbon": (38.72, -9.14), "porto": (41.16, -8.63), "algarve": (37.10, -8.25),
        "faro": (37.02, -7.94),
    }

    show_invest = settings.SHOW_INVESTMENT_FEATURES

    def _map_pin(prop) -> dict:
        lat = float(prop.latitude) if prop.latitude is not None else None
        lon = float(prop.longitude) if prop.longitude is not None else None
        if lat is None or lon is None:
            city_key = prop.city.name.lower()
            coords = CITY_COORDS.get(city_key)
            if coords:
                lat, lon = coords
        m = prop.metric if hasattr(prop, "metric") and prop.metric else None
        def _dec(v):
            return float(v) if isinstance(v, Decimal) else (v or 0)
        return {
            "id": prop.pk,
            "title": prop.title,
            "city": prop.city.name,
            "country": prop.country.name,
            "price": f"{prop.currency} {int(prop.price):,}",
            "type": prop.get_property_type_display(),
            "beds": prop.bedrooms,
            "area": int(prop.area_sqm) if prop.area_sqm else None,
            # Investment fields are nulled out in ads-safe mode so the map popup
            # never surfaces ROI / yield / score.
            "score": (m.investment_score if m else None) if show_invest else None,
            "roi_min": (_dec(m.estimated_roi_min) if m else 0) if show_invest else None,
            "roi_max": (_dec(m.estimated_roi_max) if m else 0) if show_invest else None,
            "yield": (_dec(m.rental_yield) if m else 0) if show_invest else None,
            "lat": lat,
            "lon": lon,
        }

    _hx_target = (request.headers.get("HX-Target") or "").strip()
    _target_id = _hx_target[1:] if _hx_target.startswith("#") else _hx_target
    is_results_partial = bool(request.headers.get("HX-Request")) and _target_id == "results"

    map_props_json = (
        json.dumps([_map_pin(i) for i in items]) if not is_results_partial else "[]"
    )

    ctx = {
        "items": items,
        "countries": countries,
        "types": PropertyType.choices,
        "params": p,
        "ordering": ordering,
        "page": page,
        "total": total,
        "has_next": page * page_size < total,
        "has_prev": page > 1,
        "next_page": page + 1,
        "prev_page": page - 1,
        "map_props_json": map_props_json,
        "show_compare": True,
    }
    template = "web/_marketplace_grid.html" if is_results_partial else "web/marketplace.html"
    return render(request, template, ctx)


def property_detail(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(
        Property.objects.select_related("country", "city", "metric", "owner")
        .prefetch_related("images", "tags"),
        pk=pk,
    )
    Property.objects.filter(pk=prop.pk).update(views_count=F("views_count") + 1)

    # Track recently-viewed listings in the session (most-recent first, capped).
    try:
        recent = [i for i in request.session.get("recent_views", []) if i != prop.pk]
        recent.insert(0, prop.pk)
        request.session["recent_views"] = recent[:12]
    except Exception:
        pass

    similar_qs = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images")
        .filter(country=prop.country, property_type=prop.property_type, status="active")
        .exclude(pk=prop.pk)
    )
    if settings.SHOW_INVESTMENT_FEATURES:
        similar = list(similar_qs.order_by("-metric__investment_score")[:4])
    else:
        similar = list(similar_qs.order_by("-is_featured", "-created_at")[:4])
    is_favorited = (
        request.user.is_authenticated
        and Favorite.objects.filter(user=request.user, property=prop).exists()
    )

    # Default simulator output for the right-rail / share card.
    sim = simulate_for_property(prop) if settings.SHOW_INVESTMENT_FEATURES else None

    # Local market insight from the city + country baselines.
    city_insight = {
        "avg_price_sqm": float(prop.city.avg_price_sqm) if prop.city.avg_price_sqm else None,
        "avg_rental_yield": float(prop.city.avg_rental_yield) if prop.city.avg_rental_yield else None,
        "investment_score": prop.city.investment_score,
        "demand": prop.city.demand or prop.country.base_demand,
        "trend": prop.city.trend or prop.country.base_trend,
        "risk": prop.city.risk or prop.country.base_risk,
        "population": prop.city.population,
        "summary": prop.city.summary,
        "country_summary": prop.country.summary,
    }

    from apps.web.seo_helpers import property_json_ld, property_meta_description

    from apps.web.services.og_image import absolute_og_url

    seo_title = f"{prop.title} · {prop.city.name} · Vivalty"
    seo_description = property_meta_description(prop)
    # Dynamic, branded share card (photo + price + location overlay).
    seo_image = absolute_og_url(prop)

    return render(
        request,
        "web/property_detail.html",
        {
            "p": prop,
            "similar": similar,
            "lead_form": LeadForm(),
            "is_favorited": is_favorited,
            "simulation": sim,
            "city_insight": city_insight,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "seo_image": seo_image,
            "property_json_ld": property_json_ld(prop),
        },
    )


def quiz(request: HttpRequest) -> HttpResponse:
    """Dream-home matchmaker — a shareable lifestyle quiz."""
    from apps.web.services.quiz import QUESTIONS

    return render(request, "web/quiz.html", {"questions_json": json.dumps(QUESTIONS)})


@require_POST
def quiz_result(request: HttpRequest) -> HttpResponse:
    """Score the quiz answers and return the result fragment (HTMX swap)."""
    from apps.web.services import destinations as dest
    from apps.web.services.quiz import QUESTIONS, score_answers

    valid_ids = {q["id"] for q in QUESTIONS}
    answers = {k: v for k, v in request.POST.items() if k in valid_ids}
    code, budget = score_answers(answers)

    guide = dest.guide_by_code(code)
    country = Country.objects.filter(code=code).first()

    listings = []
    if country is not None:
        listings = list(
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images")
            .filter(status=Status.ACTIVE, country=country, price__lte=budget)
            .order_by("-is_featured", "-created_at")[:3]
        )
        if not listings:
            listings = list(
                Property.objects.select_related("country", "city", "metric")
                .prefetch_related("images")
                .filter(status=Status.ACTIVE, country=country)
                .order_by("price")[:3]
            )

    flag = country.flag_emoji if country else "📍"
    return render(
        request,
        "web/components/quiz_result.html",
        {
            "guide": guide,
            "country": country,
            "flag": flag,
            "listings": listings,
            "budget": budget,
        },
    )


def property_og_image(request: HttpRequest, pk: int) -> HttpResponse:
    """Dynamic 1200×630 share card for a listing (cached)."""
    from django.core.cache import cache

    from apps.web.services.og_image import render_property_og

    prop = get_object_or_404(
        Property.objects.select_related("country", "city").prefetch_related("images"),
        pk=pk,
    )

    ts = int(prop.updated_at.timestamp()) if prop.updated_at else 0
    cache_key = f"og:property:{pk}:{ts}"

    # Cache is a nice-to-have; never let a cache outage break the share card.
    png = None
    try:
        png = cache.get(cache_key)
    except Exception:
        logger.warning("OG cache read failed", exc_info=True)

    if png is None:
        try:
            png = render_property_og(prop)
        except Exception:
            logger.exception("OG render failed for property %s", pk)
            # Redirect to the static fallback so the tag still resolves.
            return redirect(f"{settings.SITE_URL.rstrip('/')}/static/img/og-image.png")
        try:
            cache.set(cache_key, png, 60 * 60 * 24 * 7)
        except Exception:
            logger.warning("OG cache write failed", exc_info=True)

    resp = HttpResponse(png, content_type="image/png")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


def property_story(request: HttpRequest, pk: int) -> HttpResponse:
    """Vertical 9:16 slideshow for TikTok/Reels — screen-record friendly."""
    prop = get_object_or_404(
        Property.objects.select_related("country", "city").prefetch_related("images"),
        pk=pk,
    )
    story_images: list[str] = []
    for img in prop.images.all():
        if img.url:
            story_images.append(img.url)
    if not story_images:
        primary = prop.primary_image_url
        if primary:
            story_images.append(primary)
    if not story_images:
        story_images.append(
            "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=1080&q=80"
        )

    return render(
        request,
        "web/property_story.html",
        {
            "p": prop,
            "story_images": story_images,
            "story_images_json": json.dumps(story_images),
            "seo_title": f"{prop.title} · Story · Vivalty",
        },
    )


def price_explorer(request: HttpRequest) -> HttpResponse:
    """Interactive 'what does €X buy?' comparison across destinations."""
    from apps.web.services.price_compare import budget_presets, compare_budget

    budget = _safe_int(request.GET.get("budget"), 300_000)
    budget = max(50_000, min(5_000_000, budget))
    rows = compare_budget(float(budget))
    site = settings.SITE_URL.rstrip("/")

    return render(
        request,
        "web/price_explorer.html",
        {
            "budget": budget,
            "presets": budget_presets(),
            "rows": rows,
            "share_url": f"{site}/explore/prices/?budget={budget}",
            "seo_title": f"What does €{budget:,} buy abroad? · Vivalty".replace(",", " "),
            "seo_description": (
                f"See what €{budget:,} can buy across Portugal, Spain, France, Italy, "
                "the UK, the UAE and Switzerland — real listings, no financial advice."
            ).replace(",", " "),
        },
    )


def destinations_index(request: HttpRequest) -> HttpResponse:
    """Hub page linking to every country destination guide (ads-safe SEO)."""
    from apps.web.services import destinations as dest

    guides = dest.all_guides()
    codes = [g.code for g in guides]

    countries = {c.code: c for c in Country.objects.filter(code__in=codes)}
    counts = {
        row["country__code"]: row["n"]
        for row in (
            Property.objects.filter(status=Status.ACTIVE, country__code__in=codes)
            .values("country__code")
            .annotate(n=Count("id"))
        )
    }

    cards = []
    for g in guides:
        country = countries.get(g.code)
        cards.append(
            {
                "guide": g,
                "country": country,
                "listings_count": counts.get(g.code, 0),
                "cities": list(country.cities.all()[:4]) if country else [],
            }
        )

    return render(
        request,
        "web/destinations_index.html",
        {"cards": cards, "total_listings": sum(counts.values())},
    )


def destination_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Per-country destination guide: lifestyle, neighbourhoods, buying steps, FAQ."""
    from apps.web.services import destinations as dest

    guide = dest.guide_by_slug(slug)
    if guide is None:
        from django.http import Http404

        raise Http404("Unknown destination")

    country = Country.objects.filter(code=guide.code).first()

    cities = []
    listings = []
    listings_count = 0
    if country is not None:
        cities = list(
            country.cities.annotate(
                listings_count=Count("properties", filter=Q(properties__status=Status.ACTIVE))
            ).order_by(F("population").desc(nulls_last=True))
        )
        listings_qs = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images")
            .filter(status=Status.ACTIVE, country=country)
            .order_by("-is_featured", "-created_at")
        )
        listings_count = listings_qs.count()
        listings = list(listings_qs[:6])

    # FAQ JSON-LD for rich results.
    faq_ld = None
    if guide.faqs:
        faq_ld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.question,
                        "acceptedAnswer": {"@type": "Answer", "text": f.answer},
                    }
                    for f in guide.faqs
                ],
            },
            ensure_ascii=False,
        )

    hero_image = guide.hero_image
    for p in listings:
        if p.primary_image_url:
            hero_image = p.primary_image_url
            break

    # "Other destinations" rail — (code, slug, name, flag) excluding current.
    flags = {c.code: c.flag_emoji for c in Country.objects.filter(code__in=[g.code for g in dest.all_guides()])}
    other_destinations = [
        (g.code, g.slug, g.name, flags.get(g.code, "📍"))
        for g in dest.all_guides()
        if g.code != guide.code
    ]

    from apps.web.services import city_guides as cg

    city_guide_slugs = {s for (c, s) in cg.all_city_guide_keys() if c == guide.code}

    seo_title = f"Buying property in {guide.name} — a buyer's guide · Vivalty"

    return render(
        request,
        "web/destination_detail.html",
        {
            "guide": guide,
            "country": country,
            "cities": cities,
            "city_guide_slugs": city_guide_slugs,
            "listings": listings,
            "listings_count": listings_count,
            "hero_image": hero_image,
            "OTHER_DESTINATIONS": other_destinations,
            "faq_json_ld": faq_ld,
            "seo_title": seo_title,
            "seo_description": guide.meta_description,
            "seo_image": hero_image,
        },
    )


def city_destination_detail(
    request: HttpRequest, country_slug: str, city_slug: str
) -> HttpResponse:
    """City-level guide — e.g. Living in Lisbon, Buying in Dubai Marina."""
    from django.http import Http404

    from apps.web.services import city_guides as cg
    from apps.web.services import destinations as dest

    country_guide = dest.guide_by_slug(country_slug)
    if country_guide is None:
        raise Http404("Unknown destination")

    city_guide = cg.city_guide(country_guide.code, city_slug)
    if city_guide is None:
        raise Http404("Unknown city guide")

    country = Country.objects.filter(code=country_guide.code).first()
    city_obj = (
        City.objects.filter(country=country, slug=city_slug).first()
        if country is not None
        else None
    )

    listings: list[Property] = []
    listings_count = 0
    if city_obj is not None:
        listings_qs = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images")
            .filter(status=Status.ACTIVE, city=city_obj)
            .order_by("-is_featured", "-created_at")
        )
        listings_count = listings_qs.count()
        listings = list(listings_qs[:6])

    faq_ld = None
    if city_guide.faqs:
        faq_ld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.question,
                        "acceptedAnswer": {"@type": "Answer", "text": f.answer},
                    }
                    for f in city_guide.faqs
                ],
            },
            ensure_ascii=False,
        )

    hero_image = city_guide.hero_image
    for p in listings:
        if p.primary_image_url:
            hero_image = p.primary_image_url
            break

    seo_title = f"Living in {city_guide.name} — buyer's guide · Vivalty"

    return render(
        request,
        "web/city_destination.html",
        {
            "country_guide": country_guide,
            "city_guide": city_guide,
            "country": country,
            "city": city_obj,
            "listings": listings,
            "listings_count": listings_count,
            "hero_image": hero_image,
            "faq_json_ld": faq_ld,
            "seo_title": seo_title,
            "seo_description": city_guide.meta_description,
            "seo_image": hero_image,
        },
    )


def markets(request: HttpRequest) -> HttpResponse:
    if not settings.SHOW_INVESTMENT_FEATURES:
        return redirect("web:marketplace")
    countries = (
        Country.objects.annotate(
            cities_count=Count("cities", distinct=True),
            heat_avg_score=Avg("cities__investment_score"),
            heat_avg_yield=Avg("cities__avg_rental_yield"),
            listings_count=Count("properties", filter=Q(properties__status="active"), distinct=True),
        )
        .order_by("name")
    )
    cities = (
        City.objects.select_related("country")
        .annotate(listings_count=Count("properties", filter=Q(properties__status="active")))
        .order_by(F("investment_score").desc(nulls_last=True))[:30]
    )
    # Heatmap data (country-level avg score & yield).
    heatmap = [
        {
            "code": c.code,
            "name": c.name,
            "flag": c.flag_emoji,
            "score": int(c.heat_avg_score or 0),
            "yield": float(c.heat_avg_yield or 0),
            "roi_min": float(c.base_roi_min or 0),
            "roi_max": float(c.base_roi_max or 0),
            "risk": c.base_risk,
            "trend": c.base_trend,
            "listings": c.listings_count,
        }
        for c in countries
    ]
    return render(
        request,
        "web/markets.html",
        {
            "countries": countries,
            "cities": cities,
            "heatmap_json": json.dumps(heatmap),
        },
    )


def methodology(request: HttpRequest) -> HttpResponse:
    """How Our AI Score Works — transparent factor breakdown + data sources."""
    if not settings.SHOW_INVESTMENT_FEATURES:
        return redirect("web:marketplace")

    factors = [
        {
            "key": "yield",
            "label": "Rental yield",
            "max": FACTOR_WEIGHTS["yield"],
            "icon": "📈",
            "desc": "Gross rental yield estimated from city benchmarks and the asking price. "
                    "Each 1% of yield earns 5 points, capped at 40.",
            "sources": [
                "City avg €/m² and rental yield benchmarks",
                "Country base rental yield",
                "Listing's asking price + area",
            ],
        },
        {
            "key": "demand",
            "label": "Rental demand",
            "max": FACTOR_WEIGHTS["demand"],
            "icon": "🏘️",
            "desc": "Local rental demand classification (low / medium / high) tied to the city, "
                    "with country fallback when city signal is unavailable.",
            "sources": [
                "City demand classification (admin-curated)",
                "Country base demand",
            ],
        },
        {
            "key": "trend",
            "label": "Market trend",
            "max": FACTOR_WEIGHTS["trend"],
            "icon": "📊",
            "desc": "Twelve-month price trend (declining / stable / growth). Growing markets earn the full 20 points.",
            "sources": [
                "City trend (admin-curated)",
                "Country trend baseline",
            ],
        },
        {
            "key": "value_for_money",
            "label": "Value for money",
            "max": FACTOR_WEIGHTS["value_for_money"],
            "icon": "💰",
            "desc": "Implied price per m² versus the city benchmark. Up to +10 when priced ≥15% below city average; "
                    "−8 when priced ≥25% above.",
            "sources": ["City €/m² benchmark", "Listing area + price"],
        },
        {
            "key": "verification",
            "label": "Verification",
            "max": FACTOR_WEIGHTS["verification"],
            "icon": "🛡️",
            "desc": "Editorial review by Vivalty's editorial desk. +5 when the listing has been verified.",
            "sources": ["Vivalty editorial review", "Agency credentials"],
        },
        {
            "key": "risk_penalty",
            "label": "Country / city risk",
            "max": FACTOR_WEIGHTS["risk_penalty"],
            "icon": "⚠️",
            "desc": "Subtracted from the raw score — up to −18 points for elevated jurisdiction risk.",
            "sources": ["Country / city risk classification (low / medium / high)"],
        },
    ]

    data_sources = [
        {
            "title": "Public market benchmarks",
            "icon": "🏛️",
            "items": [
                "INSEE & Notaires de France (FR pricing)",
                "ONS / Land Registry (UK pricing)",
                "Idealista, Tinsa & INE (ES pricing)",
                "Wüest Partner & SNB (CH pricing)",
                "Idealista.it & OMI (IT pricing)",
                "DXB Land & Property Monitor (AE pricing)",
                "Confidencial Imobiliário & INE (PT pricing)",
            ],
        },
        {
            "title": "Rental yield references",
            "icon": "📐",
            "items": [
                "Country and city-level yield benchmarks (admin-curated)",
                "Listing-level yield estimates derived from asking price ÷ market rent",
                "Tourist short-let benchmarks for Algarve, Florence, Dubai",
            ],
        },
        {
            "title": "Macro & risk inputs",
            "icon": "🌐",
            "items": [
                "OECD & IMF country economic outlooks",
                "ECB & SNB policy rate guidance",
                "Local property tax / acquisition fee schedules",
            ],
        },
        {
            "title": "Vivalty proprietary signals",
            "icon": "🧠",
            "items": [
                "Editorial verification by the Vivalty editorial desk",
                "Agency credential checks",
                "User-engagement signal aggregation (saved, viewed, contacted)",
            ],
        },
    ]

    confidence_levels = [
        ("Verified", "bg-emerald-100 text-emerald-700",
         "City-level data + listing-level data are both present and recent."),
        ("Estimated", "bg-amber-100 text-amber-700",
         "Some city or listing inputs use country-level fallbacks — refine with admin overrides."),
        ("Country baseline", "bg-rose-100 text-rose-700",
         "Only country baseline data is available. Yield, demand and trend are country-wide."),
    ]

    investor_form = InvestorInquiryForm()
    return render(
        request,
        "web/methodology.html",
        {
            "factors": factors,
            "data_sources": data_sources,
            "confidence_levels": confidence_levels,
            "weights_total": sum(w for k, w in FACTOR_WEIGHTS.items() if k != "risk_penalty"),
            "investor_form": investor_form,
        },
    )


def compare(request: HttpRequest) -> HttpResponse:
    if not settings.SHOW_INVESTMENT_FEATURES:
        return redirect("web:marketplace")
    raw_ids = (request.GET.get("ids") or "").replace(" ", "")
    pk_list: list[int] = []
    for part in raw_ids.split(","):
        if not part:
            continue
        try:
            pk_list.append(int(part))
        except ValueError:
            continue
        if len(pk_list) >= 4:
            break

    props: list = []
    sims: list = []
    if pk_list:
        props = list(
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images", "tags")
            .filter(pk__in=pk_list, status="active")
        )
        order_map = {pk: i for i, pk in enumerate(pk_list)}
        props.sort(key=lambda x: order_map.get(x.pk, 99))
        sims = [simulate_for_property(p) for p in props]

    rows = list(zip(props, sims)) if props else []

    return render(
        request,
        "web/compare.html",
        {
            "rows": rows,
            "compare_properties": props,
            "requested_ids": pk_list,
        },
    )


# ─── Legal & compliance pages (ad-platform landing-page requirements) ───────

def _legal_page(
    request: HttpRequest,
    template: str,
    *,
    page_title: str,
    page_subtitle: str = "",
    breadcrumb_label: str = "",
) -> HttpResponse:
    return render(
        request,
        template,
        {
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "breadcrumb_label": breadcrumb_label or page_title,
        },
    )


def privacy_policy(request: HttpRequest) -> HttpResponse:
    return _legal_page(
        request,
        "web/legal/privacy.html",
        page_title="Privacy Policy",
        page_subtitle="How we collect, use and protect your personal information.",
        breadcrumb_label="Privacy Policy",
    )


def terms_of_service(request: HttpRequest) -> HttpResponse:
    return _legal_page(
        request,
        "web/legal/terms.html",
        page_title="Terms of Service",
        page_subtitle="Rules for using the Vivalty marketplace and research tools.",
        breadcrumb_label="Terms of Service",
    )


def cookie_policy(request: HttpRequest) -> HttpResponse:
    return _legal_page(
        request,
        "web/legal/cookies.html",
        page_title="Cookie Policy",
        page_subtitle="How we use cookies and similar technologies.",
        breadcrumb_label="Cookies",
    )


def legal_notice(request: HttpRequest) -> HttpResponse:
    return _legal_page(
        request,
        "web/legal/legal_notice.html",
        page_title="Legal Notice",
        page_subtitle="Publisher information and regulatory disclosures.",
        breadcrumb_label="Legal notice",
    )


def contact(request: HttpRequest) -> HttpResponse:
    return _legal_page(
        request,
        "web/legal/contact.html",
        page_title="Contact",
        page_subtitle="Get in touch with the Vivalty team.",
        breadcrumb_label="Contact",
    )


def simulator(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Standalone investment simulator. When `pk` is given we pre-fill with
    the property's current asking price + yield so investors can iterate on
    a real listing.
    """
    if not settings.SHOW_INVESTMENT_FEATURES:
        return redirect("web:marketplace")
    prop = None
    if pk:
        prop = get_object_or_404(
            Property.objects.select_related("country", "city", "metric"), pk=pk
        )

    # Default scenario inputs — read from query string for shareable links.
    p = request.GET
    default_country = (prop.country.code if prop else (p.get("country") or "PT"))
    default_price = _safe_float(
        p.get("price"),
        float(prop.price) if prop else 350_000.0,
    )
    default_yield = _safe_float(
        p.get("yield"),
        float(prop.metric.rental_yield) if (prop and getattr(prop, "metric", None) and prop.metric.rental_yield) else 5.5,
    )
    inputs = SimulatorInputs(
        price=default_price,
        currency=(prop.currency if prop else (p.get("currency") or "EUR")),
        country_code=default_country,
        rental_yield_pct=default_yield,
        down_payment_pct=_safe_float(p.get("down"), 30.0),
        mortgage_years=_safe_int(p.get("years"), 25),
        mortgage_rate_pct=_safe_float(p.get("rate"), -1.0) if p.get("rate") else None,
        appreciation_pct=_safe_float(p.get("appreciation"), -1.0) if p.get("appreciation") else None,
        horizon_years=_safe_int(p.get("horizon"), 10),
    )
    if inputs.mortgage_rate_pct == -1.0:
        inputs = SimulatorInputs(**{**asdict(inputs), "mortgage_rate_pct": None})
    if inputs.appreciation_pct == -1.0:
        inputs = SimulatorInputs(**{**asdict(inputs), "appreciation_pct": None})

    result = simulate(inputs)
    return render(
        request,
        "web/simulator.html",
        {
            "prop": prop,
            "inputs": inputs,
            "sim": result,
            "country_assumptions_json": json.dumps(COUNTRY_ASSUMPTIONS),
            "countries": Country.objects.order_by("name"),
        },
    )


@require_POST
def simulator_compute(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint that re-runs the simulator and swaps the result panel."""
    if not settings.SHOW_INVESTMENT_FEATURES:
        return HttpResponse(status=404)
    p = request.POST
    pk = _safe_int(p.get("property_id"), 0)
    prop = None
    if pk:
        prop = (
            Property.objects.select_related("country", "city", "metric").filter(pk=pk).first()
        )

    inputs = SimulatorInputs(
        price=_safe_float(p.get("price"), float(prop.price) if prop else 350_000.0),
        currency=(prop.currency if prop else (p.get("currency") or "EUR")),
        country_code=(prop.country.code if prop else (p.get("country") or "PT")),
        rental_yield_pct=_safe_float(p.get("rental_yield_pct"), 5.5),
        down_payment_pct=_safe_float(p.get("down_payment_pct"), 30.0),
        mortgage_years=_safe_int(p.get("mortgage_years"), 25),
        mortgage_rate_pct=_safe_float(p.get("mortgage_rate_pct"), -1.0) if p.get("mortgage_rate_pct") else None,
        appreciation_pct=_safe_float(p.get("appreciation_pct"), -1.0) if p.get("appreciation_pct") else None,
        horizon_years=_safe_int(p.get("horizon_years"), 10),
    )
    if inputs.mortgage_rate_pct == -1.0:
        inputs = SimulatorInputs(**{**asdict(inputs), "mortgage_rate_pct": None})
    if inputs.appreciation_pct == -1.0:
        inputs = SimulatorInputs(**{**asdict(inputs), "appreciation_pct": None})

    result = simulate(inputs)
    return render(
        request,
        "web/components/simulator_result.html",
        {"sim": result, "inputs": inputs, "prop": prop},
    )


@require_POST
def home_quick_sim(request: HttpRequest) -> HttpResponse:
    """Lite homepage simulator. Returns a compact result panel for live,
    slider-driven underwriting without leaving the landing page.
    """
    if not settings.SHOW_INVESTMENT_FEATURES:
        return HttpResponse(status=404)
    p = request.POST
    country = (p.get("country") or "PT").upper()
    inputs = SimulatorInputs(
        price=_safe_float(p.get("price"), 350_000.0),
        currency=(p.get("currency") or "EUR"),
        country_code=country,
        rental_yield_pct=_safe_float(p.get("rental_yield_pct"), 6.0),
        down_payment_pct=_safe_float(p.get("down_payment_pct"), 30.0),
        mortgage_years=25,
        horizon_years=10,
    )
    result = simulate(inputs)
    return render(
        request,
        "web/components/quick_sim_result.html",
        {"sim": result, "quick_sim_country": country},
    )


@login_required
@require_POST
def home_favorite_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle a favorite from a home-page card and swap the small heart icon."""
    prop = get_object_or_404(Property, pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, property=prop)
    if not created:
        fav.delete()
        favorited = False
    else:
        favorited = True
    return render(
        request,
        "web/components/fav_heart.html",
        {"p": prop, "is_favorited": favorited},
    )


_SAVED_SEARCH_KEYS = (
    "search", "country", "city", "type", "price_min", "price_max",
    "score_min", "roi_min", "purpose", "max_rent", "max_budget", "ordering",
)


@login_required
@require_POST
def save_search(request: HttpRequest) -> HttpResponse:
    """Persist the user's current marketplace filters as a SavedSearch."""
    from django.http import QueryDict

    from apps.web.models import SavedSearch
    from apps.web.services import listing_filters

    # Collect known filter keys from the POST (sent as hidden inputs).
    clean = QueryDict(mutable=True)
    for key in _SAVED_SEARCH_KEYS:
        val = (request.POST.get(key) or "").strip()
        if val:
            clean[key] = val

    country_names = {c.code: c.name for c in Country.objects.all()}
    label = listing_filters.describe_filters(clean, country_names=country_names)
    query = clean.urlencode()

    # Avoid duplicates for the same user + filter set.
    existing = SavedSearch.objects.filter(user=request.user, query=query).first()
    if existing:
        saved = existing
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active"])
        created = False
    else:
        saved = SavedSearch.objects.create(
            user=request.user, label=label, query=query
        )
        created = True

    return render(
        request,
        "web/components/save_search_button.html",
        {"saved": saved, "just_saved": True, "created": created},
    )


@login_required
@require_POST
def saved_search_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete one of the current user's saved searches (HTMX → removes the row)."""
    from apps.web.models import SavedSearch

    SavedSearch.objects.filter(pk=pk, user=request.user).delete()
    return HttpResponse("")


@require_POST
def newsletter_subscribe(request: HttpRequest) -> HttpResponse:
    """Capture an email for the monthly market-intelligence roundup.

    Persisted as an InvestorInquiry (source_page="newsletter_home") so the
    growth desk sees signups alongside other leads — no separate model needed.
    """
    email = (request.POST.get("email") or "").strip()
    if email:
        from apps.web.models import InvestorInquiry

        InvestorInquiry.objects.create(
            name="Newsletter subscriber",
            email=email[:254],
            source_page="newsletter_home",
            message="Monthly market-intelligence subscription.",
        )
    return render(request, "web/components/newsletter_success.html")


def smart_search(request: HttpRequest) -> HttpResponse:
    """“Find the best investment under your budget.”

    Ranks active listings by AI score subject to a budget ceiling and optional
    market filter. Renders the result fragment for HTMX swap on the home page.
    """
    p = request.GET
    budget = _safe_float(p.get("budget"), 500_000.0)
    country = (p.get("country") or "").strip().upper()
    horizon = _safe_int(p.get("horizon"), 10)

    qs = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images")
        .filter(status="active", price__lte=budget)
    )
    if country:
        qs = qs.filter(country__code=country)
    if settings.SHOW_INVESTMENT_FEATURES:
        qs = qs.order_by("-metric__investment_score", "-metric__rental_yield")
    else:
        qs = qs.order_by("-is_featured", "-created_at")

    items = list(qs[:6])
    enriched = []
    for prop in items:
        sim = simulate_for_property(prop, horizon_years=horizon) if settings.SHOW_INVESTMENT_FEATURES else None
        enriched.append({"p": prop, "sim": sim})

    return render(
        request,
        "web/components/smart_search_results.html",
        {
            "items": enriched,
            "budget": budget,
            "country": country,
            "horizon": horizon,
        },
    )


@require_http_methods(["POST"])
def investor_inquiry(request: HttpRequest) -> HttpResponse:
    form = InvestorInquiryForm(request.POST)
    nxt = request.POST.get("next") or reverse("web:home")
    if form.is_valid():
        obj = form.save(commit=False)
        obj.source_page = (request.POST.get("source_page") or "")[:120]
        obj.save()
        messages.success(
            request,
            "Thank you. Our advisory desk typically responds within one business day.",
        )
    else:
        messages.error(request, "Please check the form fields and try again.")
    return redirect(nxt)


# ─── Auth ───────────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/m", block=False)
@ratelimit(key="ip", rate="100/h", block=False)
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    if getattr(request, "limited", False):
        messages.error(request, "Too many attempts. Please try again in a minute.")
        return render(request, "web/login.html", {"form": EmailLoginForm(request)})

    form = EmailLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        auth_login(request, user)
        messages.success(request, "Welcome back.")
        return redirect(request.GET.get("next") or "web:dashboard")

    # Surface a friendlier error when the credentials are correct but the
    # account is still pending email verification.
    if request.method == "POST" and not form.is_valid():
        raw_email = (request.POST.get("username") or "").lower().strip()
        if raw_email:
            pending = User.objects.filter(email__iexact=raw_email, is_active=False, email_verified=False).first()
            if pending:
                messages.info(
                    request,
                    "Almost there — please confirm your email. We just resent the verification link.",
                )
                try:
                    send_verification_email(pending)
                except Exception:
                    pass
                return redirect("web:verify_sent")

    return render(request, "web/login.html", {"form": form})


@ratelimit(key="ip", rate="5/m", block=False)
@ratelimit(key="ip", rate="20/h", block=False)
def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    if getattr(request, "limited", False):
        messages.error(request, "Too many signup attempts. Please try again in a few minutes.")
        return render(
            request,
            "web/register.html",
            {
                "form": RegisterForm(request=request),
                "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
            },
        )

    form = RegisterForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            send_verification_email(user)
        except Exception:
            # Don't leak the user's existence/state if the email provider hiccups.
            # The user can still trigger a resend from the verify-sent page.
            messages.warning(
                request,
                "We couldn't send your verification email right now. You can request a new one below.",
            )
        return redirect("web:verify_sent")

    return render(
        request,
        "web/register.html",
        {"form": form, "turnstile_site_key": settings.TURNSTILE_SITE_KEY},
    )


def verify_sent_view(request: HttpRequest) -> HttpResponse:
    """Friendly 'check your inbox' page. Also accepts a POST to resend."""
    if request.method == "POST":
        raw_email = (request.POST.get("email") or "").lower().strip()
        if raw_email:
            user = User.objects.filter(email__iexact=raw_email).first()
            if user and not user.email_verified:
                try:
                    send_verification_email(user)
                except Exception:
                    pass
        messages.success(request, "If an account exists for that email, we just sent a fresh verification link.")
        return redirect("web:verify_sent")
    return render(request, "web/auth/verify_sent.html")


@ratelimit(key="ip", rate="30/m", block=False)
def verify_email_view(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Confirm an email by uid+token, then activate and auto-login the user."""
    if getattr(request, "limited", False):
        messages.error(request, "Too many verification attempts. Please slow down.")
        return redirect("web:verify_sent")
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "web/auth/verify_failed.html", status=400)

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.is_active = True
        user.save(update_fields=["email_verified", "email_verified_at", "is_active"])
        try:
            send_welcome_email(user)
        except Exception:
            pass

    auth_login(request, user)
    messages.success(request, "Email confirmed. Welcome aboard!")
    return redirect("web:dashboard")


@ratelimit(key="ip", rate="3/m", block=False)
@ratelimit(key="ip", rate="10/h", block=False)
def forgot_password_view(request: HttpRequest) -> HttpResponse:
    if getattr(request, "limited", False):
        messages.error(request, "Too many requests. Please try again later.")
        return redirect("web:forgot_password")
    form = ForgotPasswordForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower().strip()
        # Don't leak which addresses exist: always show the same "sent" page.
        user = User.objects.filter(email__iexact=email).first()
        if user:
            try:
                send_password_reset_email(user)
            except Exception:
                pass
        return redirect("web:forgot_password_sent")
    return render(
        request,
        "web/auth/forgot.html",
        {"form": form, "turnstile_site_key": settings.TURNSTILE_SITE_KEY},
    )


def forgot_password_sent_view(request: HttpRequest) -> HttpResponse:
    return render(request, "web/auth/forgot_sent.html")


@ratelimit(key="ip", rate="10/m", block=False)
def password_reset_confirm_view(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    if getattr(request, "limited", False):
        messages.error(request, "Too many attempts. Please try again later.")
        return redirect("web:forgot_password")
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and default_token_generator.check_token(user, token)
    if not valid:
        return render(request, "web/auth/reset_failed.html", status=400)

    form = SetNewPasswordForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        # A password reset implicitly verifies the email, since the user proved
        # access to the inbox.
        if not user.email_verified:
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.is_active = True
            user.save(update_fields=["email_verified", "email_verified_at", "is_active"])
        auth_login(request, user)
        messages.success(request, "Password updated. You're signed in.")
        return redirect("web:dashboard")
    return render(request, "web/auth/reset.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("web:home")


# ─── Dashboard ──────────────────────────────────────────────────────────────

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    favorites = (
        Favorite.objects.select_related("property__country", "property__city", "property__metric")
        .prefetch_related("property__images", "property__tags")
        .filter(user=request.user)
    )
    mine = []
    if request.user.role in {"owner", "admin"} or request.user.is_staff:
        mine = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images", "tags")
            .filter(owner=request.user)
            .order_by("-created_at")
        )

    # Watchlist analytics — institutional-feeling KPIs at the top of the dashboard.
    fav_props = [f.property for f in favorites]
    if fav_props:
        avg_score = round(
            sum((f.property.metric.investment_score if getattr(f.property, "metric", None) else 0) for f in favorites)
            / max(1, len(favorites)),
            1,
        )
        avg_yield = round(
            sum(
                float(f.property.metric.rental_yield)
                for f in favorites
                if getattr(f.property, "metric", None) and f.property.metric.rental_yield
            )
            / max(1, len(favorites)),
            2,
        )
        total_value = sum(float(f.property.price) for f in favorites)
    else:
        avg_score, avg_yield, total_value = 0, 0, 0

    from apps.web.models import SavedSearch

    saved_searches = list(
        SavedSearch.objects.filter(user=request.user).order_by("-created_at")
    )

    return render(
        request,
        "web/dashboard.html",
        {
            "favorites": favorites,
            "mine": mine,
            "saved_searches": saved_searches,
            "watchlist_kpis": {
                "count": len(favorites),
                "avg_score": avg_score,
                "avg_yield": avg_yield,
                "total_value": total_value,
                "countries": len({p.country_id for p in fav_props}),
            },
        },
    )


# ─── List your property — multi-step wizard ────────────────────────────────
#
# Entry point: /list/  (alias: legacy /owner/new/ → 302 to /list/).
# - If the user is anonymous            → redirect to register with next=/list/
# - If the user is an investor          → /list/become-owner/ (one-screen upgrade)
# - If the user is an owner / admin / staff → wizard step 1
#
# Per-step form posts redirect to the next step. No HTMX swap on step
# transitions on purpose (browser-back works, refresh-resistant, easier to
# debug). HTMX is reserved for the live score preview, AI description
# rewrite, image uploads, and the address autocomplete.

_STEP_FORM_CLASSES = {
    "type": ListingTypeForm,
    "location": ListingLocationForm,
    "specs": ListingSpecsForm,
    "price": ListingPriceForm,
}

_STEP_TEMPLATES = {
    "type": "web/listing/_step_type.html",
    "location": "web/listing/_step_location.html",
    "specs": "web/listing/_step_specs.html",
    "photos": "web/listing/_step_photos.html",
    "price": "web/listing/_step_price.html",
}


def _is_owner_or_admin(user) -> bool:
    return user.is_staff or getattr(user, "role", None) in {Role.OWNER, Role.ADMIN}


def _initial_for_step(step: str, draft: dict) -> dict:
    """Map the session draft back onto the per-step form's `initial=` kwarg."""
    if step == "type":
        return {"title": draft.get("title"), "property_type": draft.get("property_type")}
    if step == "location":
        return {
            "country": draft.get("country_id"),
            "city": draft.get("city_id"),
            "address": draft.get("address"),
            "latitude": draft.get("latitude") or None,
            "longitude": draft.get("longitude") or None,
        }
    if step == "specs":
        return {
            "bedrooms": draft.get("bedrooms"),
            "bathrooms": draft.get("bathrooms"),
            "area_sqm": draft.get("area_sqm"),
            "year_built": draft.get("year_built"),
            "description": draft.get("description"),
        }
    if step == "price":
        return {
            "price": draft.get("price"),
            "currency": draft.get("currency") or listing_wizard.CURRENCY_BY_COUNTRY.get(
                draft.get("country_code", ""), "EUR"
            ),
            "contact_name": draft.get("contact_name"),
            "contact_email": draft.get("contact_email"),
            "contact_phone": draft.get("contact_phone"),
            "listing_agency": draft.get("listing_agency"),
            "listing_ref": draft.get("listing_ref"),
        }
    return {}


def _render_step(request: HttpRequest, step: str, form=None) -> HttpResponse:
    draft = listing_wizard.get_draft(request)
    if form is None and step in _STEP_FORM_CLASSES:
        form_cls = _STEP_FORM_CLASSES[step]
        form = form_cls(initial=_initial_for_step(step, draft))

    countries = Country.objects.order_by("name")
    cities_by_country = {}
    for city in City.objects.select_related("country").order_by("country__name", "name"):
        cities_by_country.setdefault(city.country.code, []).append(
            {"id": city.id, "name": city.name, "slug": city.slug}
        )

    ctx = {
        "step": step,
        "step_label": listing_wizard.STEP_LABELS[step],
        "form": form,
        "draft": draft,
        "progress_rows": listing_wizard.progress(draft, step),
        "prev_step": listing_wizard.prev_step(step),
        "next_step": listing_wizard.next_step(step),
        "countries": countries,
        "cities_by_country_json": json.dumps(cities_by_country),
        "property_types": PropertyType.choices,
        "score": listing_wizard.score_preview(draft) if step == "price" else None,
    }
    return render(request, "web/listing/wizard.html", {**ctx, "step_template": _STEP_TEMPLATES[step]})


@login_required
def listing_start(request: HttpRequest) -> HttpResponse:
    """Entry point: /list/. Routes investors through the upgrade form,
    owners straight to step 1.
    """
    user = request.user
    if not _is_owner_or_admin(user):
        return redirect("web:become_owner")
    return redirect("web:listing_step", step=listing_wizard.STEPS[0])


@login_required
def listing_step(request: HttpRequest, step: str) -> HttpResponse:
    """Render or process a single wizard step."""
    if step not in listing_wizard.STEPS:
        return redirect("web:listing_start")
    if not _is_owner_or_admin(request.user):
        return redirect("web:become_owner")

    if request.method == "POST":
        return _handle_step_post(request, step)
    return _render_step(request, step)


def _handle_step_post(request: HttpRequest, step: str) -> HttpResponse:
    if step == "photos":
        # Photos step has no Django Form — its content is managed via the
        # HTMX upload endpoints. Submitting just advances to the next step.
        return redirect("web:listing_step", step=listing_wizard.next_step(step) or "price")

    form_cls = _STEP_FORM_CLASSES[step]
    form = form_cls(request.POST)
    if not form.is_valid():
        return _render_step(request, step, form=form)
    listing_wizard.update_draft(request, form.to_draft())

    # Step 1 may also include a chosen property_type label for display.
    if step == "type":
        ptype = form.cleaned_data["property_type"]
        listing_wizard.update_draft(
            request, {"property_type_display": dict(PropertyType.choices).get(ptype, ptype)}
        )

    nxt = listing_wizard.next_step(step)
    if nxt is None:
        return redirect("web:listing_review")
    return redirect("web:listing_step", step=nxt)


@login_required
def listing_review(request: HttpRequest) -> HttpResponse:
    if not _is_owner_or_admin(request.user):
        return redirect("web:become_owner")
    draft = listing_wizard.get_draft(request)
    if not listing_wizard.can_review(draft):
        messages.info(request, "A few details are still missing — let's finish them first.")
        # Send them back to the first incomplete required step.
        for s in listing_wizard.STEPS:
            if not listing_wizard.is_step_complete(draft, s):
                return redirect("web:listing_step", step=s)
        return redirect("web:listing_start")

    return render(
        request,
        "web/listing/review.html",
        {
            "draft": draft,
            "score": listing_wizard.score_preview(draft),
            "progress_rows": listing_wizard.progress(draft, "price"),
            "step_labels": listing_wizard.STEP_LABELS,
        },
    )


@login_required
@require_POST
def listing_publish(request: HttpRequest) -> HttpResponse:
    if not _is_owner_or_admin(request.user):
        return redirect("web:become_owner")
    try:
        prop = listing_wizard.publish_draft(request)
    except ValueError:
        messages.error(request, "Your draft is incomplete. Please review every step.")
        return redirect("web:listing_review")
    return redirect("web:listing_success", pk=prop.pk)


@login_required
def listing_success(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images"),
        pk=pk,
        owner=request.user,
    )
    return render(request, "web/listing/success.html", {"p": prop})


@login_required
def listing_cancel(request: HttpRequest) -> HttpResponse:
    """Clear the in-flight draft and return to the dashboard."""
    listing_wizard.clear_draft(request)
    messages.info(request, "Listing draft discarded.")
    return redirect("web:dashboard")


# ─── Become-owner intercept ────────────────────────────────────────────────


@login_required
def become_owner(request: HttpRequest) -> HttpResponse:
    """Investors who hit the listing flow land here for a one-screen role
    upgrade before continuing into the wizard. Owners / admins bypass.
    """
    if _is_owner_or_admin(request.user):
        return redirect("web:listing_start")

    form = BecomeOwnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.apply(request.user)
        messages.success(request, "You're set up as an owner. Let's list your first property.")
        return redirect("web:listing_start")
    return render(request, "web/listing/become_owner.html", {"form": form})


# ─── Edit / delete (post-publish, single page) ─────────────────────────────


@login_required
def listing_edit(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    if prop.owner_id != request.user.id and not (request.user.is_staff or request.user.role == Role.ADMIN):
        messages.error(request, "You can't edit this listing.")
        return redirect("web:dashboard")
    form = PropertyEditForm(request.POST or None, instance=prop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Listing updated.")
        return redirect("web:property_detail", pk=prop.pk)
    return render(request, "web/listing/edit.html", {"p": prop, "form": form})


@login_required
@require_POST
def listing_delete(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    if prop.owner_id != request.user.id and not (request.user.is_staff or request.user.role == Role.ADMIN):
        messages.error(request, "You can't delete this listing.")
        return redirect("web:dashboard")
    title = prop.title
    prop.delete()
    messages.success(request, f"Listing “{title}” deleted.")
    return redirect("web:dashboard")


# ─── HTMX endpoints for the wizard ─────────────────────────────────────────


@login_required
@require_POST
def listing_score_preview(request: HttpRequest) -> HttpResponse:
    """Recompute the score preview from the in-flight price / currency
    fields (and the draft's location + area) and swap the gauge.
    """
    p = request.POST
    patch: dict = {}
    if (raw := p.get("price")) is not None and raw != "":
        patch["price"] = raw
    if (cur := p.get("currency")):
        patch["currency"] = cur
    if patch:
        listing_wizard.update_draft(request, patch)
    draft = listing_wizard.get_draft(request)
    return render(
        request,
        "web/listing/_score_preview.html",
        {"score": listing_wizard.score_preview(draft), "draft": draft},
    )


@login_required
@require_POST
def listing_ai_rewrite(request: HttpRequest) -> HttpResponse:
    """Polish the owner-typed description using the AI rewriter and swap the
    textarea contents in-place.
    """
    raw = (request.POST.get("description") or "").strip()

    if not raw:
        return render(
            request,
            "web/listing/_description_textarea.html",
            {"description": "", "polished": False, "ai_error": "Please write a description first, then click Polish with AI."},
        )

    if not settings.OPENAI_API_KEY:
        return render(
            request,
            "web/listing/_description_textarea.html",
            {
                "description": raw,
                "polished": False,
                "ai_error": "AI rewrite is not configured — add OPENAI_API_KEY to your .env file.",
            },
        )

    draft = listing_wizard.get_draft(request)
    try:
        polished = listing_ai.rewrite_description(
            raw,
            context={
                "title": draft.get("title"),
                "property_type": draft.get("property_type_display") or draft.get("property_type"),
                "city_name": draft.get("city_name"),
                "country_name": draft.get("country_name"),
                "area_sqm": draft.get("area_sqm"),
                "bedrooms": draft.get("bedrooms"),
                "bathrooms": draft.get("bathrooms"),
            },
        )
    except Exception:
        logger.exception("listing_ai_rewrite failed")
        return render(
            request,
            "web/listing/_description_textarea.html",
            {"description": raw, "polished": False, "ai_error": "AI rewrite failed — please try again in a moment."},
        )

    listing_wizard.update_draft(request, {"description": polished})
    return render(
        request,
        "web/listing/_description_textarea.html",
        {"description": polished, "polished": polished != raw},
    )


@login_required
def listing_price_suggest(request: HttpRequest) -> HttpResponse:
    """Render an inline price suggestion chip for the price step, given the
    draft's city and area.
    """
    draft = listing_wizard.get_draft(request)
    city = None
    country = None
    if draft.get("city_id"):
        city = City.objects.select_related("country").filter(pk=draft["city_id"]).first()
    if draft.get("country_id"):
        country = Country.objects.filter(pk=draft["country_id"]).first()
    area = None
    if draft.get("area_sqm"):
        try:
            area = Decimal(str(draft["area_sqm"]))
        except (InvalidOperation, TypeError, ValueError):
            area = None
    suggestion = listing_ai.suggest_price(city=city, country=country, area_sqm=area)
    return render(request, "web/listing/_price_suggestion.html", {"s": suggestion})


@login_required
@require_POST
def listing_image_upload(request: HttpRequest) -> HttpResponse:
    """Receive one or more file uploads and append them to the draft stash.
    Returns the refreshed image grid fragment.
    """
    files = request.FILES.getlist("images") or ([request.FILES["image"]] if "image" in request.FILES else [])
    if not files:
        return HttpResponseBadRequest("No file uploaded.")
    for fh in files:
        if fh.size > 8 * 1024 * 1024:  # 8 MB per image
            messages.error(request, f"“{fh.name}” is over the 8 MB per-image limit.")
            continue
        if not (fh.content_type or "").startswith("image/"):
            messages.error(request, f"“{fh.name}” is not an image.")
            continue
        listing_wizard.add_image(request, fh)
    return render(
        request,
        "web/listing/_image_grid.html",
        {"images": listing_wizard.get_draft(request).get("images", [])},
    )


@login_required
@require_POST
def listing_image_url(request: HttpRequest) -> HttpResponse:
    """Append a paste-URL image to the draft and refresh the grid."""
    raw = (request.POST.get("url") or "").strip()
    if raw and (raw.startswith("http://") or raw.startswith("https://")):
        listing_wizard.add_image_url(request, raw)
    else:
        messages.error(request, "Paste a valid http(s) image URL.")
    return render(
        request,
        "web/listing/_image_grid.html",
        {"images": listing_wizard.get_draft(request).get("images", [])},
    )


@login_required
@require_POST
def listing_image_delete(request: HttpRequest, image_id: str) -> HttpResponse:
    listing_wizard.remove_image(request, image_id)
    return render(
        request,
        "web/listing/_image_grid.html",
        {"images": listing_wizard.get_draft(request).get("images", [])},
    )


@login_required
def listing_address_search(request: HttpRequest) -> HttpResponse:
    """Address autocomplete via Nominatim. Used by the location step."""
    query = (request.GET.get("q") or "").strip()
    country_code = (request.GET.get("cc") or "").strip().upper() or None
    suggestions = geocoding.search(query, country_code=country_code, limit=6) if len(query) >= 3 else []
    return render(request, "web/listing/_address_suggestions.html", {"suggestions": suggestions})


@login_required
def owner_new_legacy(request: HttpRequest) -> HttpResponse:
    """Legacy /owner/new/ endpoint → 302 redirect to the new wizard so old
    bookmarks and the admin's "View site" link keep working.
    """
    return redirect("web:listing_start")


# ─── HTMX endpoints ─────────────────────────────────────────────────────────

@login_required
@require_POST
def favorite_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, property=prop)
    if not created:
        fav.delete()
        favorited = False
    else:
        favorited = True
    return render(
        request,
        "web/components/favorite_button.html",
        {"p": prop, "is_favorited": favorited},
    )


@require_POST
def lead_create(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    form = LeadForm(request.POST)
    if form.is_valid():
        lead = form.save(commit=False)
        lead.property = prop
        if request.user.is_authenticated:
            lead.user = request.user
        lead.save()
        Property.objects.filter(pk=prop.pk).update(leads_count=F("leads_count") + 1)
        return render(request, "web/components/lead_success.html")
    return render(request, "web/components/lead_form.html", {"p": prop, "lead_form": form})


# ─── AI advisor (server-rendered chat) ──────────────────────────────────────

@login_required
def chat(request: HttpRequest, session_id: int | None = None) -> HttpResponse:
    sessions = AIConversationSession.objects.filter(user=request.user).order_by("-updated_at")
    active = None
    messages_qs: list[ChatMessage] = []
    if session_id:
        active = get_object_or_404(AIConversationSession, pk=session_id, user=request.user)
        messages_qs = list(active.messages.all())
    elif sessions.exists():
        active = sessions.first()
        messages_qs = list(active.messages.all())
    return render(
        request,
        "web/chat.html",
        {"sessions": sessions, "active": active, "messages": messages_qs},
    )


@login_required
@require_POST
def chat_new(request: HttpRequest) -> HttpResponse:
    sess = AIConversationSession.objects.create(user=request.user)
    return redirect("web:chat_session", session_id=sess.pk)


@login_required
@require_http_methods(["POST"])
def chat_stream(request: HttpRequest, session_id: int) -> HttpResponse:
    """SSE endpoint scoped to the website (session auth + CSRF)."""
    sess = get_object_or_404(AIConversationSession, pk=session_id, user=request.user)
    payload: dict
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    message = (payload.get("message") or "").strip()
    if not message:
        return HttpResponseBadRequest()

    def event_stream() -> Iterator[bytes]:
        for delta in advisor_stream(sess, message):
            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n".encode("utf-8")
        yield b'data: {"event": "done"}\n\n'

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp

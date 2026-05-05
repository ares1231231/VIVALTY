"""Server-rendered website views.

Thin handlers — every piece of business logic lives in the existing service
layer (`apps/properties/services/scoring.py`, `apps/ai_advisor/services/*`).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Iterator

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST, require_http_methods

from apps.ai_advisor.models import AIConversationSession, ChatMessage, Role as ChatRole
from apps.ai_advisor.services.advisor import generate, stream as advisor_stream
from apps.geo.models import City, Country
from apps.properties.models import Favorite, Property, PropertyType, Status
from .forms import EmailLoginForm, LeadForm, PropertyForm, RegisterForm


# --- Public pages -----------------------------------------------------------

def home(request: HttpRequest) -> HttpResponse:
    featured = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images", "tags")
        .filter(status="active", is_featured=True)
        .order_by("-metric__investment_score")[:6]
    )
    if not featured.exists():
        featured = (
            Property.objects.select_related("country", "city", "metric")
            .prefetch_related("images", "tags")
            .filter(status="active")
            .order_by("-metric__investment_score")[:6]
        )
    countries = Country.objects.annotate(cities_count=Count("cities")).order_by("name")
    return render(request, "web/home.html", {"featured": featured, "countries": countries})


def marketplace(request: HttpRequest) -> HttpResponse:
    qs = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images", "tags")
        .filter(status="active")
    )

    p = request.GET
    if (search := p.get("search")):
        qs = qs.filter(
            Q(title__icontains=search) | Q(description__icontains=search) |
            Q(city__name__icontains=search) | Q(country__name__icontains=search)
        )
    if (country := p.get("country")):
        qs = qs.filter(country__code__iexact=country)
    if (ptype := p.get("type")):
        qs = qs.filter(property_type=ptype)
    if (price_min := p.get("price_min")):
        try: qs = qs.filter(price__gte=float(price_min))
        except ValueError: pass
    if (price_max := p.get("price_max")):
        try: qs = qs.filter(price__lte=float(price_max))
        except ValueError: pass
    if (score_min := p.get("score_min")):
        try: qs = qs.filter(metric__investment_score__gte=int(score_min))
        except ValueError: pass
    if (roi_min := p.get("roi_min")):
        try: qs = qs.filter(metric__estimated_roi_min__gte=float(roi_min))
        except ValueError: pass

    ordering = p.get("ordering") or "-is_featured,-created_at"
    qs = qs.order_by(*[o.strip() for o in ordering.split(",") if o.strip()])

    # Simple pagination
    try:
        page = max(1, int(p.get("page", 1)))
    except ValueError:
        page = 1
    page_size = 24
    total = qs.count()
    items = list(qs[(page - 1) * page_size : page * page_size])

    countries = Country.objects.order_by("name")

    # City-level approximate lat/lon lookup for map pins (no DB column needed)
    CITY_COORDS: dict[str, tuple[float, float]] = {
        "paris": (48.85, 2.35), "lyon": (45.75, 4.83), "marseille": (43.30, 5.37),
        "nice": (43.71, 7.26), "bordeaux": (44.84, -0.58), "toulouse": (43.60, 1.44),
        "london": (51.51, -0.13), "manchester": (53.48, -2.24), "birmingham": (52.48, -1.90),
        "edinburgh": (55.95, -3.19), "bristol": (51.45, -2.59),
        "madrid": (40.42, -3.70), "barcelona": (41.39, 2.15), "valencia": (39.47, -0.38),
        "seville": (37.38, -5.99), "malaga": (36.72, -4.42), "marbella": (36.51, -4.88),
        "zurich": (47.38, 8.54), "geneva": (46.20, 6.14), "basel": (47.56, 7.59),
        "rome": (41.90, 12.50), "milan": (45.47, 9.19), "florence": (43.77, 11.26),
        "venice": (45.44, 12.33), "naples": (40.85, 14.27),
        "dubai": (25.20, 55.27), "abu dhabi": (24.47, 54.37),
        "lisbon": (38.72, -9.14), "porto": (41.16, -8.63), "algarve": (37.10, -8.25),
        "faro": (37.02, -7.94),
    }

    def _map_pin(prop) -> dict:
        city_key = prop.city.name.lower()
        coords = CITY_COORDS.get(city_key)
        m = prop.metric if hasattr(prop, "metric") and prop.metric else None
        def _dec(v):
            return float(v) if isinstance(v, Decimal) else (v or 0)
        return {
            "id": prop.pk,
            "title": prop.title,
            "city": prop.city.name,
            "country": prop.country.name,
            "price": f"{prop.currency} {int(prop.price):,}",
            "score": m.investment_score if m else None,
            "roi_min": _dec(m.estimated_roi_min) if m else 0,
            "roi_max": _dec(m.estimated_roi_max) if m else 0,
            "yield": _dec(m.rental_yield) if m else 0,
            "lat": coords[0] if coords else None,
            "lon": coords[1] if coords else None,
        }

    map_props_json = json.dumps([_map_pin(i) for i in items]) if not request.headers.get("HX-Request") else "[]"

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
    }
    template = "web/_marketplace_grid.html" if request.headers.get("HX-Request") else "web/marketplace.html"
    return render(request, template, ctx)


def property_detail(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(
        Property.objects.select_related("country", "city", "metric", "owner")
        .prefetch_related("images", "tags"),
        pk=pk,
    )
    Property.objects.filter(pk=prop.pk).update(views_count=F("views_count") + 1)
    similar = (
        Property.objects.select_related("country", "city", "metric")
        .prefetch_related("images")
        .filter(country=prop.country, property_type=prop.property_type, status="active")
        .exclude(pk=prop.pk)
        .order_by("-metric__investment_score")[:4]
    )
    is_favorited = (
        request.user.is_authenticated
        and Favorite.objects.filter(user=request.user, property=prop).exists()
    )
    return render(
        request,
        "web/property_detail.html",
        {"p": prop, "similar": similar, "lead_form": LeadForm(), "is_favorited": is_favorited},
    )


def markets(request: HttpRequest) -> HttpResponse:
    countries = Country.objects.annotate(cities_count=Count("cities")).order_by("name")
    cities = (
        City.objects.select_related("country")
        .order_by(F("investment_score").desc(nulls_last=True))[:30]
    )
    return render(request, "web/markets.html", {"countries": countries, "cities": cities})


# --- Auth -------------------------------------------------------------------

def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    form = EmailLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        messages.success(request, "Welcome back.")
        return redirect(request.GET.get("next") or "web:dashboard")
    return render(request, "web/login.html", {"form": form})


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(request, "Account created.")
        return redirect("web:dashboard")
    return render(request, "web/register.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("web:home")


# --- Dashboard --------------------------------------------------------------

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
    return render(request, "web/dashboard.html", {"favorites": favorites, "mine": mine})


@login_required
def owner_new(request: HttpRequest) -> HttpResponse:
    if request.user.role not in {"owner", "admin"} and not request.user.is_staff:
        messages.error(request, "Only owners / agencies can create listings.")
        return redirect("web:dashboard")
    form = PropertyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        prop = form.save(owner=request.user)
        messages.success(request, "Listing published.")
        return redirect("web:property_detail", pk=prop.pk)
    return render(request, "web/owner_new.html", {"form": form})


# --- HTMX endpoints ---------------------------------------------------------

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


# --- AI advisor (server-rendered chat) --------------------------------------

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
    """SSE endpoint scoped to the website (session auth + CSRF).

    The browser POSTs the message with the CSRF token and consumes the SSE stream
    via vanilla fetch + ReadableStream. Each frame is JSON: {"delta": "..."} and
    the final frame is {"event": "done"}.
    """
    sess = get_object_or_404(AIConversationSession, pk=session_id, user=request.user)
    payload: dict
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    message = (payload.get("message") or "").strip()
    if not message:
        return HttpResponse(status=400)

    def event_stream() -> Iterator[bytes]:
        for delta in advisor_stream(sess, message):
            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n".encode("utf-8")
        yield b'data: {"event": "done"}\n\n'

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp

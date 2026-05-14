"""Template helpers for the website."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

import markdown as md

register = template.Library()


CURRENCY_SYMBOL = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF ", "AED": "AED "}


@register.filter
def money(value, currency: str = "EUR") -> str:
    if value in (None, ""):
        return "—"
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return f"{value} {currency}"
    sym = CURRENCY_SYMBOL.get((currency or "EUR").upper(), f"{currency} ")
    formatted = f"{n:,.0f}".replace(",", " ")
    return f"{sym}{formatted}"


@register.filter
def pct(value, digits: int = 1) -> str:
    if value in (None, ""):
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{n:.{digits}f}%"


SCORE_TIERS = (
    (85, "Excellent", "bg-emerald-500 text-white"),
    (70, "Strong", "bg-emerald-400 text-emerald-900"),
    (55, "Solid", "bg-amber-400 text-amber-900"),
    (40, "Average", "bg-orange-300 text-orange-900"),
    (0, "Cautious", "bg-rose-300 text-rose-900"),
)


@register.filter
def score_label(score) -> str:
    if score in (None, ""):
        return "N/A"
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "N/A"
    return next((label for threshold, label, _ in SCORE_TIERS if s >= threshold), "Cautious")


@register.filter
def score_color(score) -> str:
    if score in (None, ""):
        return "bg-slate-200 text-slate-700"
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "bg-slate-200 text-slate-700"
    return next((color for threshold, _, color in SCORE_TIERS if s >= threshold), "bg-rose-300 text-rose-900")


RISK_COLORS = {
    "low": "bg-emerald-50 text-emerald-700",
    "medium": "bg-amber-50 text-amber-700",
    "high": "bg-rose-50 text-rose-700",
}
TREND_COLORS = {
    "growth": "bg-emerald-50 text-emerald-700",
    "stable": "bg-slate-100 text-slate-700",
    "declining": "bg-rose-50 text-rose-700",
}


@register.filter
def risk_color(value: str) -> str:
    return RISK_COLORS.get(value or "", "bg-slate-100 text-slate-700")


@register.filter
def trend_color(value: str) -> str:
    return TREND_COLORS.get(value or "", "bg-slate-100 text-slate-700")


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs) -> str:
    """Re-build the current querystring with one or more keys replaced.

    Example: <a href="?{% query_replace page=2 %}">Next</a>
    """
    request = context["request"]
    params = request.GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()


@register.filter(name="markdown")
def render_markdown(value: str) -> str:
    if not value:
        return ""
    html = md.markdown(value or "", extensions=["fenced_code", "tables", "nl2br"])
    return mark_safe(html)


@register.filter
def initials(user) -> str:
    if not user or not user.is_authenticated:
        return "?"
    parts = [user.first_name, user.last_name]
    letters = "".join(p[0] for p in parts if p)
    return (letters or user.email[:1]).upper()


@register.filter
def get_item(mapping, key):
    """Lookup helper for dict / list access from templates."""
    if mapping is None:
        return None
    try:
        return mapping[key]
    except (KeyError, IndexError, TypeError):
        return getattr(mapping, str(key), None)


@register.filter
def absolute(value):
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return value


CONFIDENCE_PILL = {
    "verified": ("Verified", "disclosure disclosure-verified"),
    "estimated": ("Estimated", "disclosure disclosure-estimated"),
    "baseline": ("Country baseline", "disclosure disclosure-baseline"),
}


@register.simple_tag
def confidence_pill(metric) -> str:
    """Render a disclosure pill describing how trustworthy a metric is.

    Reads `metric.is_estimated` + the city-level data presence to decide
    between Verified / Estimated / Country baseline.
    """
    if metric is None:
        label, css = CONFIDENCE_PILL["baseline"]
        return mark_safe(f'<span class="{css}">{label}</span>')
    if not metric.is_estimated:
        label, css = CONFIDENCE_PILL["verified"]
    else:
        label, css = CONFIDENCE_PILL["estimated"]
    return mark_safe(f'<span class="{css}">{label}</span>')


@register.filter
def positive_or_zero(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0

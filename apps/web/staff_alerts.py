"""Django admin banner: new signups and member logins."""

from __future__ import annotations

from datetime import datetime

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import StaffActivityAlert

SESSION_WATERMARK_KEY = "staff_alerts_watermark"
MAX_BANNER_ITEMS = 8


def _watermark_from_session(request: HttpRequest) -> datetime:
    raw = request.session.get(SESSION_WATERMARK_KEY)
    if isinstance(raw, str):
        parsed = parse_datetime(raw)
        if parsed is not None:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
    return datetime.fromtimestamp(0, tz=timezone.utc)


def staff_alerts_for_request(request: HttpRequest) -> list[StaffActivityAlert]:
    if not request.user.is_authenticated or not request.user.is_staff:
        return []
    watermark = _watermark_from_session(request)
    return list(
        StaffActivityAlert.objects.select_related("user")
        .filter(created_at__gt=watermark)
        .order_by("-created_at")[:MAX_BANNER_ITEMS]
    )


def staff_alert_banner_context(request: HttpRequest) -> dict:
    alerts = staff_alerts_for_request(request)
    extra = StaffActivityAlert.objects.filter(
        created_at__gt=_watermark_from_session(request)
    ).count() - len(alerts)
    return {
        "staff_activity_alerts": alerts,
        "staff_activity_alerts_extra": max(extra, 0),
        "staff_activity_alerts_dismiss_url": reverse("admin:staff_alerts_dismiss"),
    }


def dismiss_staff_alerts_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.user.is_staff:
        request.session[SESSION_WATERMARK_KEY] = timezone.now().isoformat()
    referer = request.META.get("HTTP_REFERER") or reverse("admin:index")
    return redirect(referer)


def patch_admin_site() -> None:
    site = admin.site
    if getattr(site, "_vivalty_staff_alerts_patched", False):
        return

    original_each_context = site.each_context

    def each_context(request: HttpRequest):
        context = original_each_context(request)
        context.update(staff_alert_banner_context(request))
        return context

    site.each_context = each_context  # type: ignore[method-assign]

    original_get_urls = site.get_urls

    def get_urls():
        custom = [
            path(
                "staff-alerts/dismiss/",
                site.admin_view(dismiss_staff_alerts_view),
                name="staff_alerts_dismiss",
            ),
        ]
        return custom + original_get_urls()

    site.get_urls = get_urls  # type: ignore[method-assign]
    site._vivalty_staff_alerts_patched = True  # type: ignore[attr-defined]

"""HTTP middleware for the public website."""

from __future__ import annotations

import hashlib
import logging
import os
import re

from django.conf import settings
from django.db.models import F
from django.http import HttpResponsePermanentRedirect
from django.utils import timezone

logger = logging.getLogger("vivalty.web")


class CanonicalHostMiddleware:
    """Redirect www to the apex domain (vivalty.com).

    Requires DNS: CNAME www → Railway (or Cloudflare proxy). Once www resolves,
    all traffic is permanently redirected to the canonical host so SEO and
    cookies stay on one origin.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical_host = os.getenv("CANONICAL_HOST", "vivalty.com").strip().lower()

    def __call__(self, request):
        # Use META directly so we do not trigger DisallowedHost before ALLOWED_HOSTS
        # is evaluated (e.g. Django test client, Railway internal healthchecks).
        raw_host = request.META.get("HTTP_HOST", "")
        if not raw_host:
            return self.get_response(request)
        host = raw_host.split(":")[0].lower()
        www_host = f"www.{self.canonical_host}"
        if host == www_host:
            scheme = "https" if request.is_secure() else request.scheme
            path = request.get_full_path()
            return HttpResponsePermanentRedirect(f"{scheme}://{self.canonical_host}{path}")
        return self.get_response(request)


# Paths that are noise, not "real" visits.
_SKIP_PREFIXES = (
    "/admin", "/static", "/media", "/api/", "/htmx/", "/health",
    "/robots.txt", "/sitemap", "/favicon", "/.well-known",
)

# Crawlers, previews and monitoring agents.
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|preview|monitor|pingdom|uptime|lighthouse|"
    r"headless|python-requests|curl|wget|facebookexternalhit|whatsapp|telegram",
    re.IGNORECASE,
)


class VisitTrackingMiddleware:
    """Count real page views + daily unique visitors for the admin dashboard.

    Counts only successful HTML GET responses from non-staff, non-bot clients.
    Failures are swallowed — analytics must never break a page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._track(request, response)
        except Exception:  # pragma: no cover — never let stats break a request
            logger.debug("Visit tracking failed.", exc_info=True)
        return response

    def _track(self, request, response) -> None:
        if request.method != "GET" or response.status_code != 200:
            return
        path = request.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return
        if "text/html" not in response.get("Content-Type", ""):
            return
        # HTMX fragment swaps are interactions inside a page, not page views.
        if request.headers.get("HX-Request"):
            return
        ua = request.META.get("HTTP_USER_AGENT", "")
        if not ua or _BOT_RE.search(ua):
            return
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_staff", False):
            return

        # Imported here (not at module top) because Django imports this module
        # while building the middleware chain, before the app registry loads
        # models in some deployment paths.
        from apps.web.models import DailyPageView, DailyVisitor

        today = timezone.localdate()
        row, created = DailyPageView.objects.get_or_create(
            date=today, path=path[:300], defaults={"count": 1}
        )
        if not created:
            DailyPageView.objects.filter(pk=row.pk).update(count=F("count") + 1)

        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "")
        )
        visitor_hash = hashlib.sha1(
            f"{settings.SECRET_KEY}:{today}:{ip}:{ua}".encode()
        ).hexdigest()
        DailyVisitor.objects.get_or_create(date=today, visitor_hash=visitor_hash)

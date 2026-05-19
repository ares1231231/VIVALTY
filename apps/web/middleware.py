"""HTTP middleware for the public website."""

from __future__ import annotations

import os

from django.http import HttpResponsePermanentRedirect


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

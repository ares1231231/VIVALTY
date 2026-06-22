"""Top-level URL routing for the Vivalty API."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import JsonResponse
from django.urls import include, path

from apps.web.sitemaps import (
    CityGuideSitemap,
    DestinationSitemap,
    PropertySitemap,
    StaticViewSitemap,
)
from apps.web.views import robots_txt
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


def health(_request):
    return JsonResponse({"status": "ok", "service": "vivalty-api"})


sitemaps = {
    "static": StaticViewSitemap,
    "destinations": DestinationSitemap,
    "city_guides": CityGuideSitemap,
    "properties": PropertySitemap,
}

api_v1 = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/", include("apps.users.urls")),
    path("geo/", include("apps.geo.urls")),
    path("", include("apps.properties.urls")),
    path("ai/", include("apps.ai_advisor.urls")),
    path("billing/", include("apps.billing.urls")),
]

urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemap",
    ),
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/v1/", include(api_v1)),
    # Server-rendered website (Django templates + Tailwind + HTMX).
    # Mounted last so /admin/, /health/ and /api/v1/ take precedence.
    path("", include("apps.web.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

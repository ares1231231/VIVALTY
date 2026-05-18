from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "web"

# Permanent (301) redirects from the legacy /simulator/* paths to the new
# /ai-invest/* canonical URLs. Preserves query strings and the `pk` kwarg.
_simulator_legacy_redirect = RedirectView.as_view(
    pattern_name="web:simulator", permanent=True, query_string=True
)
_simulator_property_legacy_redirect = RedirectView.as_view(
    pattern_name="web:simulator_property", permanent=True, query_string=True
)

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),

    path("", views.home, name="home"),
    path("marketplace/", views.marketplace, name="marketplace"),
    path("properties/<int:pk>/", views.property_detail, name="property_detail"),
    path("markets/", views.markets, name="markets"),
    path("methodology/", views.methodology, name="methodology"),
    path("compare/", views.compare, name="compare"),

    # AI Invest — new canonical paths. The URL `name` stays "simulator" so
    # every existing {% url 'web:simulator' %} call continues to work.
    path("ai-invest/", views.simulator, name="simulator"),
    path("ai-invest/<int:pk>/", views.simulator, name="simulator_property"),

    # Legacy /simulator/* paths → 301 redirect to the canonical /ai-invest/*.
    path("simulator/", _simulator_legacy_redirect),
    path("simulator/<int:pk>/", _simulator_property_legacy_redirect),

    path("investor-inquiry/", views.investor_inquiry, name="investor_inquiry"),

    path("auth/login/",    views.login_view,    name="login"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/logout/",   views.logout_view,   name="logout"),

    # Email verification
    path("auth/verify/sent/", views.verify_sent_view, name="verify_sent"),
    path("auth/verify/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify_email"),

    # Password reset
    path("auth/forgot/",      views.forgot_password_view,      name="forgot_password"),
    path("auth/forgot/sent/", views.forgot_password_sent_view, name="forgot_password_sent"),
    path("auth/reset/<str:uidb64>/<str:token>/", views.password_reset_confirm_view, name="password_reset_confirm"),

    path("dashboard/", views.dashboard, name="dashboard"),

    # ── List your property — wizard ───────────────────────────────────────
    path("list/",                 views.listing_start,    name="listing_start"),
    path("list/become-owner/",    views.become_owner,     name="become_owner"),
    path("list/review/",          views.listing_review,   name="listing_review"),
    path("list/publish/",         views.listing_publish,  name="listing_publish"),
    path("list/success/<int:pk>/", views.listing_success, name="listing_success"),
    path("list/cancel/",          views.listing_cancel,   name="listing_cancel"),
    path("list/<int:pk>/edit/",   views.listing_edit,     name="listing_edit"),
    path("list/<int:pk>/delete/", views.listing_delete,   name="listing_delete"),
    path("list/<str:step>/",      views.listing_step,     name="listing_step"),

    # Legacy /owner/new/ → 302 to the new wizard so admin "View site" links keep working.
    path("owner/new/", views.owner_new_legacy, name="owner_new"),

    # HTMX endpoints
    path("htmx/properties/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("htmx/properties/<int:pk>/lead/", views.lead_create, name="lead_create"),
    path("htmx/simulator/", views.simulator_compute, name="simulator_compute"),
    path("htmx/smart-search/", views.smart_search, name="smart_search"),

    # HTMX endpoints for the listing wizard
    path("htmx/list/score-preview/",   views.listing_score_preview,  name="listing_score_preview"),
    path("htmx/list/ai-rewrite/",      views.listing_ai_rewrite,     name="listing_ai_rewrite"),
    path("htmx/list/price-suggest/",   views.listing_price_suggest,  name="listing_price_suggest"),
    path("htmx/list/upload/",          views.listing_image_upload,   name="listing_image_upload"),
    path("htmx/list/image-url/",       views.listing_image_url,      name="listing_image_url"),
    path("htmx/list/image/<str:image_id>/delete/", views.listing_image_delete, name="listing_image_delete"),
    path("htmx/list/address-search/",  views.listing_address_search, name="listing_address_search"),

    # AI advisor
    path("chat/", views.chat, name="chat"),
    path("chat/new/", views.chat_new, name="chat_new"),
    path("chat/<int:session_id>/", views.chat, name="chat_session"),
    path("chat/<int:session_id>/stream/", views.chat_stream, name="chat_stream"),
]

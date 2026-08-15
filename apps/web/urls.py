from django.urls import path
from django.views.generic import RedirectView
from django.views.i18n import set_language

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

# 301 redirect: /listings/ → /marketplace/
# Preserves any query string (?country=, ?type=, etc.) so old bookmarks
# and external links land on a fully-filtered marketplace page.
_listings_legacy_redirect = RedirectView.as_view(
    pattern_name="web:marketplace", permanent=True, query_string=True
)

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("i18n/setlang/", set_language, name="set_language"),

    path("", views.home, name="home"),
    path("marketplace/", views.marketplace, name="marketplace"),
    path(
        "marketplace/<str:country_code>/",
        views.marketplace_country,
        name="marketplace_country",
    ),
    path(
        "properties/<slug:slug>/<int:pk>/",
        views.property_detail,
        name="property_detail_seo",
    ),
    path("properties/<int:pk>/", views.property_detail, name="property_detail"),
    path("properties/<int:pk>/og.png", views.property_og_image, name="property_og"),
    path("properties/<int:pk>/story/", views.property_story, name="property_story"),

    # Destination guides (ads-safe SEO landing pages)
    path("destinations/", views.destinations_index, name="destinations"),
    path(
        "destinations/<slug:country_slug>/<slug:city_slug>/",
        views.city_destination_detail,
        name="city_destination",
    ),
    path("destinations/<slug:slug>/", views.destination_detail, name="destination_detail"),

    # Price comparison explorer
    path("explore/prices/", views.price_explorer, name="price_explorer"),

    # Dream-home matchmaker quiz
    path("quiz/", views.quiz, name="quiz"),
    path("htmx/quiz/result/", views.quiz_result, name="quiz_result"),

    path("markets/", views.markets, name="markets"),
    path("methodology/", views.methodology, name="methodology"),
    path("compare/", views.compare, name="compare"),

    # Legal & compliance (required for Google Ads / TikTok Ads landing-page review)
    path("privacy/", views.privacy_policy, name="privacy"),
    path("terms/", views.terms_of_service, name="terms"),
    path("cookies/", views.cookie_policy, name="cookies"),
    path("legal/", views.legal_notice, name="legal_notice"),
    path("contact/", views.contact, name="contact"),
    path("agencies/", views.agencies, name="agencies"),

    # AI Invest — new canonical paths. The URL `name` stays "simulator" so
    # every existing {% url 'web:simulator' %} call continues to work.
    path("ai-invest/", views.simulator, name="simulator"),
    path("ai-invest/<int:pk>/", views.simulator, name="simulator_property"),

    # Legacy /simulator/* paths → 301 redirect to the canonical /ai-invest/*.
    path("simulator/", _simulator_legacy_redirect),
    path("simulator/<int:pk>/", _simulator_property_legacy_redirect),

    # Legacy /listings/ → 301 redirect to the canonical /marketplace/.
    path("listings/", _listings_legacy_redirect),

    path("investor-inquiry/", views.investor_inquiry, name="investor_inquiry"),

    path("auth/login/",    views.login_view,    name="login"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/logout/",   views.logout_view,   name="logout"),

    # Email verification
    path("auth/verify/sent/", views.verify_sent_view, name="verify_sent"),
    path("analytics/ack-sign-up/", views.analytics_ack_sign_up, name="analytics_ack_sign_up"),
    path("auth/verify/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify_email"),

    # Password reset
    path("auth/forgot/",      views.forgot_password_view,      name="forgot_password"),
    path("auth/forgot/sent/", views.forgot_password_sent_view, name="forgot_password_sent"),
    path("auth/reset/<str:uidb64>/<str:token>/", views.password_reset_confirm_view, name="password_reset_confirm"),

    path("dashboard/", views.dashboard, name="dashboard"),

    # ── Sell your property — public landing + listing wizard ──────────────
    path("sell/",                 views.sell_landing,     name="sell"),
    path("list/",                 views.listing_start,    name="listing_start"),
    path("list/become-owner/",    views.become_owner,     name="become_owner"),
    path("list/review/",          views.listing_review,   name="listing_review"),
    path("list/publish/",         views.listing_publish,  name="listing_publish"),
    path("list/publish/continue/", views.listing_publish_continue, name="listing_publish_continue"),
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
    path("leads/<int:pk>/status/", views.lead_status_update, name="lead_status_update"),
    path("htmx/simulator/", views.simulator_compute, name="simulator_compute"),
    path("htmx/smart-search/", views.smart_search, name="smart_search"),

    # Home-page interactive widgets
    path("htmx/home/quick-sim/", views.home_quick_sim, name="home_quick_sim"),
    path("htmx/home/favorite/<int:pk>/", views.home_favorite_toggle, name="home_favorite_toggle"),
    path("htmx/newsletter/", views.newsletter_subscribe, name="newsletter_subscribe"),

    # Saved searches + email alerts
    path("htmx/saved-search/save/", views.save_search, name="save_search"),
    path("htmx/saved-search/<int:pk>/delete/", views.saved_search_delete, name="saved_search_delete"),

    # HTMX endpoints for the listing wizard
    path("htmx/list/score-preview/",   views.listing_score_preview,  name="listing_score_preview"),
    path("htmx/list/ai-rewrite/",      views.listing_ai_rewrite,     name="listing_ai_rewrite"),
    path("htmx/list/price-suggest/",   views.listing_price_suggest,  name="listing_price_suggest"),
    path("htmx/list/upload/",          views.listing_image_upload,   name="listing_image_upload"),
    path("htmx/list/image-url/",       views.listing_image_url,      name="listing_image_url"),
    path("htmx/list/image/<str:image_id>/delete/", views.listing_image_delete, name="listing_image_delete"),
    path("htmx/list/address-search/",  views.listing_address_search, name="listing_address_search"),
    path("htmx/list/city-search/",     views.listing_city_search,    name="listing_city_search"),

    # AI advisor
    path("chat/", views.chat, name="chat"),
    path("chat/new/", views.chat_new, name="chat_new"),
    path("chat/<int:session_id>/", views.chat, name="chat_session"),
    path("chat/<int:session_id>/stream/", views.chat_stream, name="chat_stream"),
]

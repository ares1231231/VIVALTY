from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("marketplace/", views.marketplace, name="marketplace"),
    path("properties/<int:pk>/", views.property_detail, name="property_detail"),
    path("markets/", views.markets, name="markets"),

    path("auth/login/", views.login_view, name="login"),
    path("auth/register/", views.register_view, name="register"),
    path("auth/logout/", views.logout_view, name="logout"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("owner/new/", views.owner_new, name="owner_new"),

    # HTMX endpoints
    path("htmx/properties/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("htmx/properties/<int:pk>/lead/", views.lead_create, name="lead_create"),

    # AI advisor
    path("chat/", views.chat, name="chat"),
    path("chat/new/", views.chat_new, name="chat_new"),
    path("chat/<int:session_id>/", views.chat, name="chat_session"),
    path("chat/<int:session_id>/stream/", views.chat_stream, name="chat_stream"),
]

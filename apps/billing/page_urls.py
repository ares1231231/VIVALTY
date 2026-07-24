"""Website-facing billing URLs (the DRF plan API stays in ``urls.py``)."""

from django.urls import path

from . import page_views

app_name = "billing"

urlpatterns = [
    path("pricing/", page_views.pricing, name="pricing"),
    path("billing/feature/<int:pk>/", page_views.feature_checkout, name="feature_checkout"),
    path("billing/subscribe/<slug:code>/", page_views.plan_checkout, name="plan_checkout"),
    path("billing/success/", page_views.checkout_success, name="checkout_success"),
    path("billing/cancel/", page_views.checkout_cancel, name="checkout_cancel"),
    path("billing/webhook/", page_views.stripe_webhook, name="stripe_webhook"),
]

"""Server-rendered billing pages: pricing, checkout redirects, Stripe webhook.

The DRF plan API lives in ``views.py``; these are the website-facing views.
Checkout is Stripe-hosted — we only redirect out and fulfill via webhook.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.billing.models import Plan, Subscription
from apps.billing.services import stripe_service
from apps.properties.models import Property

logger = logging.getLogger("vivalty.billing")


def pricing(request: HttpRequest) -> HttpResponse:
    plans = Plan.objects.filter(is_active=True).order_by("monthly_price")
    current_plan_code = ""
    if request.user.is_authenticated:
        active = (
            Subscription.objects.filter(user=request.user, status__in=["active", "trialing"])
            .select_related("plan")
            .first()
        )
        if active:
            current_plan_code = active.plan.code
    return render(
        request,
        "billing/pricing.html",
        {
            "plans": plans,
            "current_plan_code": current_plan_code,
            "stripe_enabled": stripe_service.stripe_enabled(),
            "boost_price": settings.FEATURED_BOOST_PRICE_EUR,
            "boost_days": settings.FEATURED_BOOST_DAYS,
        },
    )


@login_required
@require_POST
def feature_checkout(request: HttpRequest, pk: int) -> HttpResponse:
    prop = get_object_or_404(Property, pk=pk)
    if prop.owner_id != request.user.pk and not request.user.is_staff:
        return HttpResponse(status=403)
    if prop.is_featured:
        messages.info(request, "This listing is already featured.")
        return redirect("web:dashboard")
    if not stripe_service.stripe_enabled():
        messages.error(request, "Payments are not configured yet. Please try again later.")
        return redirect("web:dashboard")
    try:
        url = stripe_service.create_featured_checkout_session(request.user, prop)
    except Exception:
        logger.exception("Failed to create featured checkout for property %s", pk)
        messages.error(request, "We couldn't start the payment. Please try again.")
        return redirect("web:dashboard")
    return redirect(url)


@login_required
@require_POST
def plan_checkout(request: HttpRequest, code: str) -> HttpResponse:
    plan = get_object_or_404(Plan, code=code, is_active=True)
    interval = request.POST.get("interval", "monthly")
    if plan.monthly_price <= 0:
        messages.info(request, "You're on the free plan by default — no payment needed.")
        return redirect("billing:pricing")
    if not stripe_service.stripe_enabled():
        messages.error(request, "Payments are not configured yet. Please try again later.")
        return redirect("billing:pricing")
    try:
        url = stripe_service.create_plan_checkout_session(request.user, plan, interval)
    except Exception:
        logger.exception("Failed to create plan checkout for %s", code)
        messages.error(request, "We couldn't start the payment. Please try again.")
        return redirect("billing:pricing")
    return redirect(url)


def checkout_success(request: HttpRequest) -> HttpResponse:
    messages.success(
        request,
        "Payment received — thank you! Your upgrade activates within a minute.",
    )
    return redirect("web:dashboard")


def checkout_cancel(request: HttpRequest) -> HttpResponse:
    messages.info(request, "Payment canceled — nothing was charged.")
    return redirect("web:dashboard")


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    if not stripe_service.stripe_enabled():
        return HttpResponse(status=503)
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe_service.verify_webhook(request.body, sig_header)
    except Exception:
        logger.warning("Rejected Stripe webhook with invalid signature.")
        return HttpResponse(status=400)
    try:
        stripe_service.handle_event(event)
    except Exception:
        # Return 500 so Stripe retries the delivery.
        logger.exception("Error handling Stripe event %s", event.get("type"))
        return HttpResponse(status=500)
    return HttpResponse(status=200)

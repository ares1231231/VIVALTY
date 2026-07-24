"""Stripe integration — Checkout Sessions + webhook fulfillment.

Two products:
    - Featured boost : one-off payment that surfaces a listing on home +
                       marketplace for FEATURED_BOOST_DAYS days.
    - Plan           : recurring subscription (monthly / yearly) for owners
                       and agencies.

Design notes:
    - Stripe-hosted Checkout only (no card data ever touches our servers).
    - Prices are created inline via ``line_items.price_data`` so no Dashboard
      product setup is required — the DB ``Plan`` rows are the source of truth.
    - ``payment_method_types`` is deliberately never passed: Stripe's dynamic
      payment methods pick the best options per customer.
    - Fulfillment happens ONLY in the webhook (never on the success redirect),
      and is idempotent via ``external_ref`` so replayed events are harmless.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import FeaturedListingPurchase, Plan, Subscription
from apps.properties.models import Property
from apps.users.models import User

logger = logging.getLogger("vivalty.billing")

# Tags checkout flows in the Stripe Dashboard (suffix is a fixed random label).
INTEGRATION_ID = "vivalty-checkout-wqzxkmpr"


def stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _client():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _absolute(path: str) -> str:
    return settings.SITE_URL.rstrip("/") + path


# ─── Checkout sessions ────────────────────────────────────────────────────

def create_featured_checkout_session(user: User, prop: Property) -> str:
    """Return a Stripe-hosted Checkout URL for a one-off featured boost."""
    stripe = _client()
    days = settings.FEATURED_BOOST_DAYS
    session = stripe.checkout.Session.create(
        mode="payment",
        integration_identifier=INTEGRATION_ID,
        client_reference_id=str(user.pk),
        customer_email=user.email or None,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "eur",
                    "unit_amount": settings.FEATURED_BOOST_PRICE_EUR * 100,
                    "product_data": {
                        "name": f"Featured boost — {prop.title[:80]}",
                        "description": f"{days} days of premium placement on Vivalty's home page and marketplace.",
                    },
                },
            }
        ],
        metadata={
            "kind": "featured",
            "property_id": str(prop.pk),
            "user_id": str(user.pk),
            "duration_days": str(days),
        },
        success_url=_absolute(reverse("billing:checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=_absolute(reverse("billing:checkout_cancel")),
    )
    return session.url


def create_plan_checkout_session(user: User, plan: Plan, interval: str) -> str:
    """Return a Stripe-hosted Checkout URL for a recurring plan subscription."""
    stripe = _client()
    if interval == "yearly":
        amount, recurring = plan.yearly_price, {"interval": "year"}
    else:
        interval = "monthly"
        amount, recurring = plan.monthly_price, {"interval": "month"}

    metadata = {
        "kind": "plan",
        "plan_code": plan.code,
        "interval": interval,
        "user_id": str(user.pk),
    }
    session = stripe.checkout.Session.create(
        mode="subscription",
        integration_identifier=INTEGRATION_ID,
        client_reference_id=str(user.pk),
        customer_email=user.email or None,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": plan.currency.lower(),
                    "unit_amount": int(Decimal(amount) * 100),
                    "recurring": recurring,
                    "product_data": {
                        "name": f"Vivalty {plan.name} ({interval})",
                        "description": plan.description[:250] or f"{plan.name} plan.",
                    },
                },
            }
        ],
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=_absolute(reverse("billing:checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=_absolute(reverse("billing:checkout_cancel")),
    )
    return session.url


# ─── Webhook fulfillment ──────────────────────────────────────────────────

def verify_webhook(payload: bytes, sig_header: str):
    """Verify the Stripe signature and return the parsed event."""
    stripe = _client()
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


def handle_event(event) -> None:
    kind = event["type"]
    obj = event["data"]["object"]
    if kind == "checkout.session.completed":
        _fulfill_checkout_session(obj)
    elif kind in ("customer.subscription.updated", "customer.subscription.deleted"):
        _sync_subscription(obj)
    else:
        logger.debug("Ignoring Stripe event %s", kind)


def _fulfill_checkout_session(session) -> None:
    meta = session.get("metadata") or {}
    if meta.get("kind") == "featured":
        _activate_featured(session, meta)
    elif meta.get("kind") == "plan":
        _activate_plan(session, meta)
    else:
        logger.warning("Checkout session %s completed without a known kind.", session.get("id"))


def _activate_featured(session, meta: dict) -> None:
    session_id = session.get("id", "")
    if FeaturedListingPurchase.objects.filter(external_ref=session_id).exists():
        return  # replayed event

    prop = Property.objects.filter(pk=meta.get("property_id")).first()
    if not prop:
        logger.error("Featured boost paid for missing property %s (%s).", meta.get("property_id"), session_id)
        return

    days = int(meta.get("duration_days") or settings.FEATURED_BOOST_DAYS)
    now = timezone.now()
    FeaturedListingPurchase.objects.create(
        property=prop,
        user=User.objects.filter(pk=meta.get("user_id")).first(),
        duration_days=days,
        amount=Decimal(session.get("amount_total") or 0) / 100,
        currency=(session.get("currency") or "eur").upper(),
        starts_at=now,
        ends_at=now + timedelta(days=days),
        external_ref=session_id,
    )
    Property.objects.filter(pk=prop.pk).update(is_featured=True)
    logger.info("Featured boost activated for property %s until +%sd (%s).", prop.pk, days, session_id)


STRIPE_STATUS_MAP = {
    "active": Subscription.Status.ACTIVE,
    "trialing": Subscription.Status.TRIALING,
    "past_due": Subscription.Status.PAST_DUE,
}


def _activate_plan(session, meta: dict) -> None:
    sub_id = session.get("subscription") or ""
    plan = Plan.objects.filter(code=meta.get("plan_code")).first()
    user = User.objects.filter(pk=meta.get("user_id")).first()
    if not (sub_id and plan and user):
        logger.error("Plan checkout %s missing subscription/plan/user (%s).", session.get("id"), meta)
        return

    stripe = _client()
    stripe_sub = stripe.Subscription.retrieve(sub_id)
    period_end = _period_end(stripe_sub)

    # One active subscription per user: retire any previous ones.
    Subscription.objects.filter(user=user, status__in=["active", "trialing", "past_due"]).exclude(
        external_ref=sub_id
    ).update(status=Subscription.Status.CANCELED, canceled_at=timezone.now())

    Subscription.objects.update_or_create(
        external_ref=sub_id,
        defaults={
            "user": user,
            "plan": plan,
            "status": STRIPE_STATUS_MAP.get(stripe_sub["status"], Subscription.Status.CANCELED),
            "current_period_end": period_end,
        },
    )
    logger.info("Subscription %s (%s) active for user %s.", sub_id, plan.code, user.pk)


def _sync_subscription(stripe_sub) -> None:
    sub = Subscription.objects.filter(external_ref=stripe_sub.get("id", "")).first()
    if not sub:
        logger.debug("Ignoring subscription event for unknown ref %s.", stripe_sub.get("id"))
        return
    status = STRIPE_STATUS_MAP.get(stripe_sub.get("status"), Subscription.Status.CANCELED)
    sub.status = status
    sub.current_period_end = _period_end(stripe_sub)
    if status == Subscription.Status.CANCELED and not sub.canceled_at:
        sub.canceled_at = timezone.now()
    sub.save(update_fields=["status", "current_period_end", "canceled_at"])


def _period_end(stripe_sub) -> datetime | None:
    # `current_period_end` lives on the subscription item in newer API versions.
    ts = stripe_sub.get("current_period_end")
    if not ts:
        items = (stripe_sub.get("items") or {}).get("data") or []
        ts = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc) if ts else None


# ─── Boost expiry (run by cron / boot script) ─────────────────────────────

def expire_featured_boosts() -> int:
    """Unfeature properties whose paid boosts have all lapsed.

    Only touches properties that were featured through a purchase — curated
    listings featured editorially (no purchase rows) are left alone.
    """
    now = timezone.now()
    expired = (
        Property.objects.filter(is_featured=True, feature_purchases__isnull=False)
        .exclude(feature_purchases__ends_at__gt=now)
        .distinct()
    )
    count = expired.update(is_featured=False)
    if count:
        logger.info("Unfeatured %d propert(ies) with lapsed boosts.", count)
    return count

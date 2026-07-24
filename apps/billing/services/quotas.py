"""Plan quota checks — listing caps and included featured slots."""

from __future__ import annotations

from django.utils import timezone

from apps.billing.models import FeaturedListingPurchase, Plan, Subscription
from apps.properties.models import Property, Status
from apps.users.models import User

# Statuses that consume a listing slot (draft/archived do not).
QUOTA_STATUSES = (Status.ACTIVE, Status.PENDING)


def get_user_plan(user: User) -> Plan:
    """Return the user's active plan, or the Free tier as default."""
    sub = (
        Subscription.objects.filter(user=user, status__in=["active", "trialing"])
        .select_related("plan")
        .first()
    )
    if sub:
        return sub.plan
    plan = Plan.objects.filter(code="free", is_active=True).first()
    if plan:
        return plan
    # Fallback if seed migration hasn't run yet.
    return Plan(
        code="free",
        name="Free",
        listing_quota=3,
        featured_quota=0,
    )


def listing_count(user: User) -> int:
    return Property.objects.filter(owner=user, status__in=QUOTA_STATUSES).count()


def featured_count(user: User) -> int:
    """Count plan-slot featuring only (paid boosts use featured_until)."""
    return (
        Property.objects.filter(owner=user, is_featured=True, featured_until__isnull=True)
        .exclude(status=Status.ARCHIVED)
        .count()
    )


def can_create_listing(user: User) -> tuple[bool, str]:
    """Whether the user may publish another listing under their plan."""
    if getattr(user, "is_staff", False):
        return True, ""
    plan = get_user_plan(user)
    used = listing_count(user)
    if used >= plan.listing_quota:
        return (
            False,
            f"You've reached the {plan.name} plan limit of {plan.listing_quota} "
            f"active listing{'s' if plan.listing_quota != 1 else ''}. "
            f"Upgrade your plan or archive a listing to free a slot.",
        )
    return True, ""


def remaining_featured_slots(user: User) -> int:
    """How many plan-included featured slots the user still has."""
    plan = get_user_plan(user)
    return max(0, plan.featured_quota - featured_count(user))


def can_apply_plan_featured(user: User) -> bool:
    return remaining_featured_slots(user) > 0


def owner_has_premium_plan(user: User) -> bool:
    """True when the user is on a paying tier (Pro / Agency)."""
    return get_user_plan(user).monthly_price > 0


def has_active_featured_purchase(prop: Property) -> bool:
    now = timezone.now()
    return FeaturedListingPurchase.objects.filter(
        property=prop, ends_at__gt=now
    ).exists()

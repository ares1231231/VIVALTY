"""Marketing-site signals (staff alerts for admin)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.users.models import User

from .models import StaffActivityAlert


def _should_notify_for(user: User) -> bool:
    return not user.is_staff and not user.is_superuser


@receiver(post_save, sender=User)
def staff_alert_on_signup(sender, instance: User, created: bool, **kwargs) -> None:
    if not created or not _should_notify_for(instance):
        return
    StaffActivityAlert.objects.create(user=instance, kind=StaffActivityAlert.Kind.SIGNUP)


@receiver(user_logged_in)
def staff_alert_on_login(sender, request, user: User, **kwargs) -> None:
    if not _should_notify_for(user):
        return
    since = timezone.now() - timedelta(hours=12)
    if StaffActivityAlert.objects.filter(
        user=user,
        kind=StaffActivityAlert.Kind.LOGIN,
        created_at__gte=since,
    ).exists():
        return
    # Skip login ping right after signup (signup alert already covers it).
    if StaffActivityAlert.objects.filter(
        user=user,
        kind=StaffActivityAlert.Kind.SIGNUP,
        created_at__gte=timezone.now() - timedelta(minutes=30),
    ).exists():
        return
    StaffActivityAlert.objects.create(user=user, kind=StaffActivityAlert.Kind.LOGIN)

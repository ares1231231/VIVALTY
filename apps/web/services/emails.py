"""Transactional email service.

In production we send through Resend; in development (no `RESEND_API_KEY`) the
console backend kicks in via `settings.EMAIL_BACKEND`, so the verify/reset
links still print to stdout and the flow remains testable end-to-end.

All public functions are idempotent in the sense that a duplicate call simply
sends another email — callers are expected to apply rate-limits upstream.
"""

from __future__ import annotations

import logging
from typing import Iterable
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator

from apps.users.models import User

logger = logging.getLogger("vivalty.emails")


# ─── Backend ──────────────────────────────────────────────────────────────

class ResendEmailBackend(BaseEmailBackend):
    """Minimal Django email backend that posts each message to Resend.

    We use the official `resend` SDK if installed; if it fails to import for
    any reason we fall back to a direct HTTP POST so an upgrade snag never
    silently swallows a verification email.
    """

    def send_messages(self, email_messages: Iterable) -> int:
        if not email_messages:
            return 0
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            logger.warning("ResendEmailBackend invoked without RESEND_API_KEY; dropping %d email(s).", len(list(email_messages)))
            return 0

        sent = 0
        for msg in email_messages:
            try:
                self._send_one(msg, api_key=api_key)
                sent += 1
            except Exception:
                logger.exception("Failed to send email via Resend to %s", msg.to)
                if not self.fail_silently:
                    raise
        return sent

    def _send_one(self, msg, *, api_key: str) -> None:
        payload = {
            "from": msg.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(msg.to),
            "subject": msg.subject,
            "text": msg.body,
        }
        if msg.cc:
            payload["cc"] = list(msg.cc)
        if msg.bcc:
            payload["bcc"] = list(msg.bcc)
        if msg.reply_to:
            payload["reply_to"] = list(msg.reply_to)

        # If the EmailMessage carries an HTML alternative, surface it as `html`.
        for alt_body, alt_mime in getattr(msg, "alternatives", []) or []:
            if alt_mime == "text/html":
                payload["html"] = alt_body
                break

        try:
            import resend  # type: ignore

            resend.api_key = api_key
            resend.Emails.send(payload)
            return
        except ImportError:
            pass

        import requests  # imported lazily to avoid a hard dep at import-time

        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        if not resp.ok:
            raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")


# ─── High-level helpers ───────────────────────────────────────────────────

def _absolute_url(path: str) -> str:
    return urljoin(settings.SITE_URL + "/", path.lstrip("/"))


def _token_pair(user: User) -> tuple[str, str]:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token


def send_verification_email(user: User) -> None:
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse

    uid, token = _token_pair(user)
    verify_url = _absolute_url(reverse("web:verify_email", args=[uid, token]))

    ctx = {
        "user": user,
        "verify_url": verify_url,
        "expires_hours": settings.EMAIL_VERIFY_TIMEOUT_HOURS,
        "site_url": settings.SITE_URL,
    }
    text_body = render_to_string("web/emails/verify.txt", ctx)
    html_body = render_to_string("web/emails/verify.html", ctx)

    msg = EmailMultiAlternatives(
        subject="Confirm your email — Vivalty",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_welcome_email(user: User) -> None:
    from django.core.mail import EmailMultiAlternatives

    ctx = {
        "user": user,
        "dashboard_url": _absolute_url("/dashboard/"),
        "marketplace_url": _absolute_url("/marketplace/"),
        "site_url": settings.SITE_URL,
    }
    text_body = render_to_string("web/emails/welcome.txt", ctx)
    html_body = render_to_string("web/emails/welcome.html", ctx)

    msg = EmailMultiAlternatives(
        subject="Welcome to Vivalty",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=True)


def send_saved_search_alert(user: User, saved_search, properties: list) -> None:
    """Email a user the new listings that match one of their saved searches."""
    from django.core.mail import EmailMultiAlternatives

    ctx = {
        "user": user,
        "search": saved_search,
        "properties": properties,
        "count": len(properties),
        "marketplace_url": _absolute_url(f"/marketplace/?{saved_search.query}"),
        "manage_url": _absolute_url("/dashboard/#saved-searches"),
        "site_url": settings.SITE_URL,
    }
    text_body = render_to_string("web/emails/saved_search_alert.txt", ctx)
    html_body = render_to_string("web/emails/saved_search_alert.html", ctx)

    n = len(properties)
    subject = f"{n} new home{'s' if n != 1 else ''} for “{saved_search.label}”"
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=True)


def send_password_reset_email(user: User) -> None:
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse

    uid, token = _token_pair(user)
    reset_url = _absolute_url(reverse("web:password_reset_confirm", args=[uid, token]))

    ctx = {
        "user": user,
        "reset_url": reset_url,
        "site_url": settings.SITE_URL,
    }
    text_body = render_to_string("web/emails/password_reset.txt", ctx)
    html_body = render_to_string("web/emails/password_reset.html", ctx)

    msg = EmailMultiAlternatives(
        subject="Reset your Vivalty password",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)

"""AI advisor persistence layer.

- AIConversationSession: chat thread, optionally pinned to a property/country.
- ChatMessage: user / assistant / system messages with RAG context snapshot.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class AIConversationSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_sessions",
        null=True,
        blank=True,
        help_text="Null = anonymous session keyed by client cookie.",
    )
    title = models.CharField(max_length=200, blank=True)

    # Optional context pins (improve grounding)
    pinned_property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_sessions",
    )
    pinned_country = models.ForeignKey(
        "geo.Country",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_sessions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def __str__(self) -> str:
        return self.title or f"Session #{self.pk}"


class ChatMessage(models.Model):
    session = models.ForeignKey(
        AIConversationSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    content = models.TextField()

    # RAG metadata: list of property IDs that were injected as context for this turn.
    context_property_ids = models.JSONField(default=list, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["session", "created_at"])]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"

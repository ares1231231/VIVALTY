from __future__ import annotations

import json
from typing import Iterator

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models import AIConversationSession
from .serializers import (
    AIConversationSessionSerializer,
    ChatMessageSerializer,
    SendMessageSerializer,
)
from .services.advisor import generate, stream as advisor_stream


class AIChatThrottle(UserRateThrottle):
    scope = "ai_chat"


def _resolve_owner(request) -> dict:
    """Sessions are scoped per-user; anonymous = staff-only sandbox sessions."""
    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user": None}


class AIConversationViewSet(viewsets.ModelViewSet):
    """CRUD for chat sessions + send / stream endpoints."""

    serializer_class = AIConversationSessionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            AIConversationSession.objects.filter(user=self.request.user)
            .prefetch_related("messages")
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        session = self.get_object()
        msgs = session.messages.all()
        return Response(ChatMessageSerializer(msgs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="send",
        throttle_classes=[AIChatThrottle],
    )
    def send(self, request, pk=None):
        """Non-streaming. POST {message: '...'} → returns full assistant message."""
        session = self.get_object()
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assistant_msg = generate(session, ser.validated_data["message"])
        return Response(
            ChatMessageSerializer(assistant_msg).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="stream",
        throttle_classes=[AIChatThrottle],
    )
    def stream(self, request, pk=None):
        """SSE streaming endpoint.

        Each event is a JSON-encoded `{"delta": "...token..."}` payload, plus
        a final `{"event": "done"}` so the client knows when to flush.
        """
        session = self.get_object()
        ser = SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        def event_stream() -> Iterator[bytes]:
            for delta in advisor_stream(session, ser.validated_data["message"]):
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n".encode("utf-8")
            yield b'data: {"event": "done"}\n\n'

        resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp

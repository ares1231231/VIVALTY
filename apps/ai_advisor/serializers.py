from __future__ import annotations

from rest_framework import serializers

from .models import AIConversationSession, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "role",
            "content",
            "context_property_ids",
            "tokens_in",
            "tokens_out",
            "created_at",
        )
        read_only_fields = fields


class AIConversationSessionSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AIConversationSession
        fields = (
            "id",
            "title",
            "pinned_property",
            "pinned_country",
            "created_at",
            "updated_at",
            "last_message",
            "message_count",
        )
        read_only_fields = ("id", "title", "created_at", "updated_at")

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        return ChatMessageSerializer(msg).data if msg else None

    def get_message_count(self, obj) -> int:
        return obj.messages.count()


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=4000)

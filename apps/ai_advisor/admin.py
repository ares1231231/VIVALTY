from django.contrib import admin

from .models import AIConversationSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("role", "content", "context_property_ids", "created_at")
    can_delete = False


@admin.register(AIConversationSession)
class AIConversationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "pinned_property", "pinned_country", "updated_at")
    list_filter = ("pinned_country",)
    search_fields = ("title", "user__email")
    inlines = (ChatMessageInline,)

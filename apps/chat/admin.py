"""Admin for chat models."""
from django.contrib import admin
from .models import ChatSession, Message


class MessageInline(admin.TabularInline):
    model = Message
    fields = ("role", "content", "tokens_used", "created_at")
    readonly_fields = ("id", "created_at")
    extra = 0
    ordering = ("created_at",)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "message_count", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("title", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MessageInline]
    filter_horizontal = ("documents",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "short_content", "tokens_used", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "session__title")
    readonly_fields = ("id", "created_at")

    def short_content(self, obj):
        return obj.content[:80]
    short_content.short_description = "Content"

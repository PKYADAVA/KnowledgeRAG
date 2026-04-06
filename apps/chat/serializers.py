"""DRF serializers for chat models."""
from rest_framework import serializers
from .models import ChatSession, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "role", "content", "sources", "model_used", "tokens_used", "created_at")
        read_only_fields = ("id", "created_at")


class ChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.ReadOnlyField()
    last_message_content = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ("id", "title", "message_count", "last_message_content", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_last_message_content(self, obj):
        msg = obj.last_message
        return msg.content[:100] if msg else None

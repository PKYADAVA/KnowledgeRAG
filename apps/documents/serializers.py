"""DRF serializers for Document models."""
from rest_framework import serializers
from .models import Document, DocumentChunk


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ("id", "chunk_index", "page_number", "content", "token_count")


class DocumentSerializer(serializers.ModelSerializer):
    file_size_display = serializers.ReadOnlyField()
    filename = serializers.ReadOnlyField()
    is_ready = serializers.ReadOnlyField()

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "file_type",
            "file_size",
            "file_size_display",
            "filename",
            "status",
            "chunk_count",
            "page_count",
            "is_ready",
            "created_at",
            "processed_at",
        )
        read_only_fields = (
            "id", "status", "chunk_count", "page_count",
            "created_at", "processed_at",
        )

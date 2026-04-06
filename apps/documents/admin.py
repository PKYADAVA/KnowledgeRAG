"""Admin for Document models."""
from django.contrib import admin
from django.utils.html import format_html
from .models import Document, DocumentChunk


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    fields = ("chunk_index", "page_number", "token_count", "content")
    readonly_fields = ("chunk_index", "page_number", "token_count", "content")
    extra = 0
    max_num = 10
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title", "owner", "file_type", "status_badge",
        "file_size_display", "chunk_count", "created_at",
    )
    list_filter = ("status", "file_type", "created_at")
    search_fields = ("title", "owner__email", "owner__username")
    readonly_fields = (
        "id", "owner", "file_size", "file_size_display",
        "chunk_count", "page_count", "created_at", "updated_at",
        "processed_at", "celery_task_id",
    )
    inlines = [DocumentChunkInline]
    ordering = ("-created_at",)

    def status_badge(self, obj):
        colors = {
            "pending": "gray",
            "processing": "yellow",
            "ready": "green",
            "failed": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background:{};padding:2px 8px;border-radius:12px;color:white">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "page_number", "token_count")
    list_filter = ("document__file_type",)
    search_fields = ("document__title", "content")
    readonly_fields = ("id", "pinecone_vector_id", "created_at")

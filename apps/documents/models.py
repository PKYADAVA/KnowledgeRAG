"""Document models — upload metadata, processing state, and chunks."""
import uuid
import os
from django.db import models
from django.conf import settings
from django.utils.text import slugify


def document_upload_path(instance, filename):
    """Store documents in per-user directories."""
    ext = filename.rsplit(".", 1)[-1].lower()
    safe_name = slugify(filename.rsplit(".", 1)[0])[:50]
    return f"uploads/{instance.owner.id}/{instance.id}/{safe_name}.{ext}"


class Document(models.Model):
    """Uploaded document with processing lifecycle."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class FileType(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "Word Document"
        TXT = "txt", "Plain Text"
        MD = "md", "Markdown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    # File metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_path)
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    file_size = models.PositiveBigIntegerField(default=0)  # bytes
    page_count = models.PositiveIntegerField(default=0)

    # Processing state
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    # Pinecone metadata
    pinecone_namespace = models.CharField(max_length=255, blank=True)
    chunk_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def file_size_display(self):
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_ready(self):
        return self.status == self.Status.READY

    @property
    def is_processing(self):
        return self.status in [self.Status.PENDING, self.Status.PROCESSING]

    def mark_processing(self, task_id=""):
        self.status = self.Status.PROCESSING
        self.celery_task_id = task_id
        self.save(update_fields=["status", "celery_task_id", "updated_at"])

    def mark_ready(self, chunk_count=0, page_count=0):
        from django.utils import timezone
        self.status = self.Status.READY
        self.chunk_count = chunk_count
        self.page_count = page_count
        self.processed_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["status", "chunk_count", "page_count", "processed_at", "error_message", "updated_at"])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.error_message = error[:2000]
        self.save(update_fields=["status", "error_message", "updated_at"])


class DocumentChunk(models.Model):
    """Individual text chunk stored after document processing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    chunk_index = models.PositiveIntegerField()
    page_number = models.PositiveIntegerField(default=0)
    pinecone_vector_id = models.CharField(max_length=255, blank=True)
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "document_chunks"
        ordering = ["chunk_index"]
        unique_together = [("document", "chunk_index")]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"

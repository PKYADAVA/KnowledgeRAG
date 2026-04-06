"""Chat session and message models."""
import uuid
from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    """A conversation thread linked to one or more documents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    documents = models.ManyToManyField(
        "documents.Document",
        blank=True,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_sessions"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "-updated_at"])]

    def __str__(self):
        return self.title or f"Chat {str(self.id)[:8]}"

    @property
    def last_message(self):
        return self.messages.order_by("-created_at").first()

    @property
    def message_count(self):
        return self.messages.count()

    def auto_title_from_first_message(self):
        """Set title from first user message (truncated)."""
        first = self.messages.filter(role=Message.Role.USER).first()
        if first and not self.title:
            self.title = first.content[:80]
            self.save(update_fields=["title"])


class Message(models.Model):
    """A single message in a chat session."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()

    # RAG metadata stored on assistant messages
    sources = models.JSONField(default=list, blank=True)
    model_used = models.CharField(max_length=50, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    retrieval_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["session", "created_at"])]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"

    @property
    def is_user(self):
        return self.role == self.Role.USER

    @property
    def is_assistant(self):
        return self.role == self.Role.ASSISTANT

    @property
    def formatted_sources(self):
        """Return deduplicated source list for template rendering."""
        seen = set()
        unique = []
        for src in self.sources:
            key = (src.get("document_id"), src.get("page_number", 0))
            if key not in seen:
                seen.add(key)
                unique.append(src)
        return unique

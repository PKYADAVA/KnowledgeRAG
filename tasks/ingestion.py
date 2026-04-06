"""
Celery tasks for asynchronous document ingestion.
"""
import logging
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    name="tasks.ingestion.process_document",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    queue="ingestion",
)
def process_document(self, document_id: str) -> dict:
    """
    Full ingestion pipeline for an uploaded document:
    1. Load the document file from storage.
    2. Split into chunks.
    3. Embed chunks with OpenAI.
    4. Upsert into Pinecone.
    5. Persist chunk metadata to PostgreSQL.
    6. Mark document as READY (or FAILED on error).
    """
    # Import Django models inside task to avoid AppRegistry issues
    from apps.documents.models import Document, DocumentChunk
    from services.document_processor import DocumentProcessor
    from services.vector_store import VectorStoreService

    logger.info(f"Starting ingestion for document: {document_id}")

    # ── Fetch document ────────────────────────────────────────────────────────
    try:
        doc = Document.objects.select_related("owner").get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        return {"status": "error", "reason": "Document not found"}

    doc.mark_processing(task_id=self.request.id)

    try:
        # ── Process ────────────────────────────────────────────────────────────
        processor = DocumentProcessor()
        result = processor.process(
            file_path=doc.file.path,
            file_type=doc.file_type,
            document_id=str(doc.id),
            owner_id=str(doc.owner.id),
            extra_metadata={
                "title": doc.title,
                "description": doc.description,
            },
        )

        if result.error:
            raise ValueError(result.error)

        # ── Upsert to Pinecone ─────────────────────────────────────────────────
        vs = VectorStoreService()
        vector_ids = vs.upsert_documents(
            documents=result.chunks,
            namespace=doc.pinecone_namespace,
        )
        logger.info(
            f"Upserted {len(vector_ids)} vectors for document {document_id}"
        )

        # ── Persist chunks to DB ───────────────────────────────────────────────
        chunk_objects = [
            DocumentChunk(
                document=doc,
                content=chunk.page_content,
                chunk_index=chunk.metadata["chunk_index"],
                page_number=chunk.metadata.get("page", 0),
                pinecone_vector_id=vector_ids[i] if i < len(vector_ids) else "",
                token_count=len(chunk.page_content) // 4,  # rough token estimate
            )
            for i, chunk in enumerate(result.chunks)
        ]
        DocumentChunk.objects.bulk_create(chunk_objects, ignore_conflicts=True)

        # ── Mark ready ─────────────────────────────────────────────────────────
        doc.mark_ready(
            chunk_count=result.chunk_count,
            page_count=result.page_count,
        )
        logger.info(
            f"Document {document_id} ingested: {result.chunk_count} chunks, "
            f"{result.page_count} pages"
        )
        return {
            "status": "success",
            "document_id": document_id,
            "chunks": result.chunk_count,
            "pages": result.page_count,
        }

    except Exception as exc:
        logger.exception(f"Ingestion failed for {document_id}: {exc}")

        # Retry with exponential backoff
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
        except self.MaxRetriesExceededError:
            doc.mark_failed(str(exc))
            return {"status": "failed", "document_id": document_id, "error": str(exc)}


@shared_task(
    name="tasks.ingestion.cleanup_stale_documents",
    queue="ingestion",
)
def cleanup_stale_documents() -> dict:
    """
    Periodic task: reset documents stuck in PROCESSING state for > 1 hour.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.documents.models import Document

    cutoff = timezone.now() - timedelta(hours=1)
    stale = Document.objects.filter(
        status=Document.Status.PROCESSING,
        updated_at__lt=cutoff,
    )
    count = stale.count()
    stale.update(
        status=Document.Status.FAILED,
        error_message="Processing timed out and was reset.",
    )
    if count:
        logger.warning(f"Reset {count} stale documents to FAILED status.")
    return {"reset_count": count}


@shared_task(
    name="tasks.ingestion.cleanup_old_sessions",
    queue="ingestion",
)
def cleanup_old_sessions() -> dict:
    """
    Periodic task: delete empty chat sessions older than 30 days.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.chat.models import ChatSession

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = ChatSession.objects.filter(
        updated_at__lt=cutoff,
        messages__isnull=True,
    ).delete()
    if deleted:
        logger.info(f"Cleaned up {deleted} empty chat sessions.")
    return {"deleted_sessions": deleted}

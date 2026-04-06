"""Document upload and management views."""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from .forms import DocumentUploadForm
from .models import Document
from tasks.ingestion import process_document

logger = logging.getLogger(__name__)


@login_required
def dashboard_view(request):
    """Main dashboard showing documents list."""
    documents = (
        Document.objects.filter(owner=request.user)
        .order_by("-created_at")
        .select_related("owner")
    )

    # Stats
    stats = {
        "total": documents.count(),
        "ready": documents.filter(status=Document.Status.READY).count(),
        "processing": documents.filter(
            status__in=[Document.Status.PENDING, Document.Status.PROCESSING]
        ).count(),
        "failed": documents.filter(status=Document.Status.FAILED).count(),
    }

    # Pagination
    paginator = Paginator(documents, 12)
    page = request.GET.get("page", 1)
    page_obj = paginator.get_page(page)

    return render(
        request,
        "documents/dashboard.html",
        {"page_obj": page_obj, "stats": stats},
    )


@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request):
    """Document upload page."""
    form = DocumentUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            doc = form.save(commit=False)
            doc.owner = request.user
            doc.file_size = request.FILES["file"].size

            # Determine file type from extension
            ext = doc.file.name.rsplit(".", 1)[-1].lower()
            doc.file_type = ext
            doc.pinecone_namespace = f"user_{request.user.id}"
            doc.save()

            # Trigger async ingestion
            task = process_document.delay(str(doc.id))
            doc.mark_processing(task_id=task.id)

            logger.info(f"Document queued for processing: {doc.id} (task: {task.id})")

            if request.headers.get("HX-Request"):
                # HTMX partial response
                return render(
                    request,
                    "documents/partials/document_card.html",
                    {"doc": doc},
                )

            messages.success(
                request,
                f'"{doc.title}" uploaded and queued for processing.',
            )
            return redirect("documents:dashboard")
        else:
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "documents/partials/upload_form.html",
                    {"form": form},
                    status=422,
                )
            messages.error(request, "Upload failed. Please check the form.")

    return render(request, "documents/upload.html", {"form": form})


@login_required
def document_status_view(request, doc_id):
    """HTMX polling endpoint — returns updated document card."""
    doc = get_object_or_404(Document, id=doc_id, owner=request.user)
    return render(
        request,
        "documents/partials/document_card.html",
        {"doc": doc},
    )


@login_required
@require_http_methods(["DELETE", "POST"])
def document_delete_view(request, doc_id):
    """Delete a document and its vectors."""
    doc = get_object_or_404(Document, id=doc_id, owner=request.user)
    title = doc.title

    # Delete vectors from Pinecone (fire and forget)
    try:
        from services.vector_store import VectorStoreService
        VectorStoreService().delete_document(str(doc.id), doc.pinecone_namespace)
    except Exception as e:
        logger.warning(f"Failed to delete vectors for {doc.id}: {e}")

    # Delete file from storage
    if doc.file:
        doc.file.delete(save=False)

    doc.delete()
    logger.info(f"Document deleted: {doc_id} by {request.user.email}")

    if request.headers.get("HX-Request"):
        return JsonResponse({"status": "deleted", "id": str(doc_id)})

    messages.success(request, f'"{title}" deleted.')
    return redirect("documents:dashboard")


@login_required
def document_detail_view(request, doc_id):
    """Document detail with chunk preview."""
    doc = get_object_or_404(Document, id=doc_id, owner=request.user)
    chunks = doc.chunks.all()[:10]
    return render(
        request,
        "documents/detail.html",
        {"doc": doc, "chunks": chunks},
    )

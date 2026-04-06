"""RAG status and health views."""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from services.vector_store import VectorStoreService


@staff_member_required
def rag_status_view(request):
    """Admin-only: Pinecone index stats."""
    try:
        vs = VectorStoreService()
        stats = vs.get_index_stats()
        return JsonResponse({"status": "ok", "stats": stats})
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)

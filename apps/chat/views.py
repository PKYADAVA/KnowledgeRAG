"""Chat views — session management and HTMX message handling."""
import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from apps.documents.models import Document
from .models import ChatSession, Message
from services.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


@login_required
def chat_list_view(request):
    """List all chat sessions for the user."""
    sessions = (
        ChatSession.objects.filter(owner=request.user)
        .prefetch_related("documents")
        .order_by("-updated_at")[:20]
    )
    return render(request, "chat/list.html", {"sessions": sessions})


@login_required
def new_chat_view(request):
    """Create a new chat session — optionally pre-select documents."""
    doc_ids = request.GET.getlist("docs")
    session = ChatSession.objects.create(owner=request.user)

    if doc_ids:
        docs = Document.objects.filter(
            id__in=doc_ids,
            owner=request.user,
            status=Document.Status.READY,
        )
        session.documents.set(docs)

    return redirect("chat:session", session_id=session.id)


@login_required
def chat_session_view(request, session_id):
    """Main chat page for a session."""
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    messages = session.messages.order_by("created_at")
    available_docs = Document.objects.filter(
        owner=request.user, status=Document.Status.READY
    ).order_by("-created_at")
    selected_doc_ids = list(session.documents.values_list("id", flat=True))

    return render(
        request,
        "chat/chat.html",
        {
            "session": session,
            "messages": messages,
            "available_docs": available_docs,
            "selected_doc_ids": [str(d) for d in selected_doc_ids],
        },
    )


@login_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="30/m", method="POST", block=True)
def send_message_view(request, session_id):
    """
    HTMX endpoint — receives user message, runs RAG pipeline,
    returns partial HTML with both user bubble and AI response.
    """
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)

    query = request.POST.get("query", "").strip()
    if not query:
        return HttpResponse(status=400)

    # Save user message
    user_msg = Message.objects.create(
        session=session,
        role=Message.Role.USER,
        content=query,
    )
    session.auto_title_from_first_message()

    # Get selected document namespaces
    doc_ids = list(session.documents.values_list("id", flat=True))
    namespaces = list(
        session.documents.values_list("pinecone_namespace", flat=True).distinct()
    )

    # Build conversation history for context window (last 10 messages)
    history = list(
        session.messages.exclude(id=user_msg.id)
        .order_by("-created_at")[:8]
        .values("role", "content")
    )
    history.reverse()

    try:
        pipeline = RAGPipeline()
        result = pipeline.query(
            question=query,
            namespaces=namespaces,
            document_ids=[str(d) for d in doc_ids],
            chat_history=history,
        )

        assistant_msg = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=result["answer"],
            sources=result.get("sources", []),
            model_used=result.get("model", ""),
            tokens_used=result.get("tokens_used", 0),
            retrieval_score=result.get("avg_score"),
        )

    except Exception as exc:
        logger.exception(f"RAG pipeline error for session {session_id}: {exc}")
        assistant_msg = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content="I encountered an error processing your request. Please try again.",
            sources=[],
        )

    # Return partial HTML for HTMX to append
    return render(
        request,
        "chat/partials/message_pair.html",
        {
            "user_msg": user_msg,
            "assistant_msg": assistant_msg,
        },
    )


@login_required
@require_http_methods(["POST"])
def update_session_docs_view(request, session_id):
    """HTMX: update documents selected for a session."""
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    doc_ids = request.POST.getlist("documents")
    docs = Document.objects.filter(
        id__in=doc_ids,
        owner=request.user,
        status=Document.Status.READY,
    )
    session.documents.set(docs)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "chat/partials/doc_selector.html",
            {
                "session": session,
                "available_docs": Document.objects.filter(
                    owner=request.user, status=Document.Status.READY
                ),
                "selected_doc_ids": [str(d.id) for d in docs],
            },
        )
    return redirect("chat:session", session_id=session_id)


@login_required
@require_http_methods(["DELETE", "POST"])
def delete_session_view(request, session_id):
    """Delete a chat session."""
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    session.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse(status=200, headers={"HX-Redirect": "/chat/"})
    messages_module = __import__("django.contrib.messages", fromlist=["success"])
    messages_module.success(request, "Chat session deleted.")
    return redirect("chat:list")


@login_required
def stream_message_view(request, session_id):
    """
    Streaming SSE endpoint for real-time token-by-token responses.
    Usage: EventSource('/chat/<id>/stream/?q=<query>')
    """
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    query = request.GET.get("q", "").strip()

    if not query:
        return HttpResponse("Query required", status=400)

    namespaces = list(
        session.documents.values_list("pinecone_namespace", flat=True).distinct()
    )
    doc_ids = list(session.documents.values_list("id", flat=True))

    def event_stream():
        try:
            pipeline = RAGPipeline()
            full_answer = ""
            sources = []

            for chunk in pipeline.stream(
                question=query,
                namespaces=namespaces,
                document_ids=[str(d) for d in doc_ids],
            ):
                if chunk["type"] == "token":
                    full_answer += chunk["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "sources":
                    sources = chunk["sources"]
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            # Save to DB after stream completes
            user_msg = Message.objects.create(
                session=session,
                role=Message.Role.USER,
                content=query,
            )
            Message.objects.create(
                session=session,
                role=Message.Role.ASSISTANT,
                content=full_answer,
                sources=sources,
            )
            session.auto_title_from_first_message()
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as exc:
            logger.exception(f"Stream error: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

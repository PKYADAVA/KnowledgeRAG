"""DRF API views for chat history."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions
from .models import ChatSession, Message
from .serializers import ChatSessionSerializer, MessageSerializer


@extend_schema_view(
    get=extend_schema(
        summary="List chat sessions",
        description="Returns all chat sessions owned by the authenticated user, most recently updated first.",
        tags=["Chat"],
    )
)
class ChatSessionListAPIView(generics.ListAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(owner=self.request.user).order_by("-updated_at")


@extend_schema_view(
    get=extend_schema(
        summary="List messages in a session",
        description="Returns all messages for a given chat session owned by the authenticated user, in chronological order.",
        tags=["Chat"],
    )
)
class ChatHistoryAPIView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        session = ChatSession.objects.get(pk=self.kwargs["pk"], owner=self.request.user)
        return session.messages.order_by("created_at")

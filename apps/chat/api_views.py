"""DRF API views for chat history."""
from rest_framework import generics, permissions
from .models import ChatSession, Message
from .serializers import ChatSessionSerializer, MessageSerializer


class ChatSessionListAPIView(generics.ListAPIView):
    serializer_class = ChatSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(owner=self.request.user).order_by("-updated_at")


class ChatHistoryAPIView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        session = ChatSession.objects.get(pk=self.kwargs["pk"], owner=self.request.user)
        return session.messages.order_by("created_at")

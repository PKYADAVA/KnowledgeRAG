"""DRF API views for document management."""
from rest_framework import generics, permissions
from rest_framework.throttling import UserRateThrottle
from .models import Document
from .serializers import DocumentSerializer


class UploadThrottle(UserRateThrottle):
    scope = "upload"


class DocumentListAPIView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user).order_by("-created_at")


class DocumentDetailAPIView(generics.RetrieveAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

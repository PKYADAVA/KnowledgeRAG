"""DRF API views for document management."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions
from rest_framework.throttling import UserRateThrottle
from .models import Document
from .serializers import DocumentSerializer


class UploadThrottle(UserRateThrottle):
    scope = "upload"


@extend_schema_view(
    get=extend_schema(
        summary="List documents",
        description="Returns all documents owned by the authenticated user, newest first.",
        tags=["Documents"],
    )
)
class DocumentListAPIView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user).order_by("-created_at")


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve document",
        description="Returns a single document owned by the authenticated user.",
        tags=["Documents"],
    )
)
class DocumentDetailAPIView(generics.RetrieveAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

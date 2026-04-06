"""DRF API URLs for documents."""
from django.urls import path
from .api_views import DocumentListAPIView, DocumentDetailAPIView

urlpatterns = [
    path("", DocumentListAPIView.as_view(), name="api-document-list"),
    path("<uuid:pk>/", DocumentDetailAPIView.as_view(), name="api-document-detail"),
]

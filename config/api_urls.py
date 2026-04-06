"""DRF API URL configuration."""
from django.urls import path, include

urlpatterns = [
    path("documents/", include("apps.documents.api_urls")),
    path("chat/", include("apps.chat.api_urls")),
]

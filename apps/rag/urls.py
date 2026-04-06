"""RAG app URL patterns (admin/status endpoints)."""
from django.urls import path
from . import views

app_name = "rag"

urlpatterns = [
    path("status/", views.rag_status_view, name="status"),
]

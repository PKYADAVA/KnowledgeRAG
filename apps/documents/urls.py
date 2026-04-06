"""Document app URL patterns."""
from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("upload/", views.upload_view, name="upload"),
    path("<uuid:doc_id>/", views.document_detail_view, name="detail"),
    path("<uuid:doc_id>/status/", views.document_status_view, name="status"),
    path("<uuid:doc_id>/delete/", views.document_delete_view, name="delete"),
]

"""Chat app URL patterns."""
from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.chat_list_view, name="list"),
    path("new/", views.new_chat_view, name="new"),
    path("<uuid:session_id>/", views.chat_session_view, name="session"),
    path("<uuid:session_id>/send/", views.send_message_view, name="send"),
    path("<uuid:session_id>/stream/", views.stream_message_view, name="stream"),
    path("<uuid:session_id>/docs/", views.update_session_docs_view, name="update-docs"),
    path("<uuid:session_id>/delete/", views.delete_session_view, name="delete"),
]

"""DRF API URLs for chat."""
from django.urls import path
from .api_views import ChatSessionListAPIView, ChatHistoryAPIView

urlpatterns = [
    path("sessions/", ChatSessionListAPIView.as_view(), name="api-chat-sessions"),
    path("sessions/<uuid:pk>/history/", ChatHistoryAPIView.as_view(), name="api-chat-history"),
]

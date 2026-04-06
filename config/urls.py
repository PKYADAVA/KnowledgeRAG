"""Root URL configuration for KnowledgeRAG."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Redirect root to dashboard
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),

    # App routes
    path("users/", include("apps.users.urls", namespace="users")),
    path("dashboard/", include("apps.documents.urls", namespace="documents")),
    path("chat/", include("apps.chat.urls", namespace="chat")),
    path("rag/", include("apps.rag.urls", namespace="rag")),

    # DRF API (optional, for external integrations)
    path("api/", include("config.api_urls")),

    # API Schema & Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="redoc"),
]

# Serve media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

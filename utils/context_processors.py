"""Template context processors."""
from django.conf import settings


def app_settings(request):
    """Inject commonly needed settings into all templates."""
    return {
        "APP_NAME": "KnowledgeRAG",
        "DEBUG": settings.DEBUG,
        "MAX_UPLOAD_SIZE_MB": settings.MAX_UPLOAD_SIZE_MB,
        "ALLOWED_FILE_TYPES": settings.ALLOWED_FILE_TYPES,
    }

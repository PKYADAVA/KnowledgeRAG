"""Celery application configuration."""
import os
from celery import Celery
from celery.utils.log import get_task_logger
from django.conf import settings

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("knowledgerag")

# Load config from Django settings, namespace=CELERY
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all INSTALLED_APPS
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# ─── Beat Schedule (periodic tasks) ───────────────────────────────────────────
app.conf.beat_schedule = {
    "cleanup-stale-documents": {
        "task": "tasks.ingestion.cleanup_stale_documents",
        "schedule": 3600.0,  # every hour
    },
    "cleanup-old-sessions": {
        "task": "tasks.ingestion.cleanup_old_sessions",
        "schedule": 86400.0,  # daily
    },
}

logger = get_task_logger(__name__)


@app.task(bind=True)
def debug_task(self):
    logger.info(f"Request: {self.request!r}")

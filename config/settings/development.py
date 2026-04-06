"""Development settings — verbose, no SSL, debug toolbar."""
from .base import *  # noqa: F401, F403

DEBUG = True

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Relax security for local dev
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Show emails in console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Django shell_plus auto-imports
SHELL_PLUS_IMPORTS = [
    "from apps.documents.models import Document",
    "from apps.chat.models import ChatSession, Message",
]

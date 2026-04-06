"""Custom Django middleware."""
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log each request with timing and request ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())[:8]
        request.request_id = request_id
        start = time.monotonic()

        response = self.get_response(request)

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            f"[{request_id}] {request.method} {request.path} "
            f"→ {response.status_code} ({duration_ms:.1f}ms) "
            f"user={getattr(request.user, 'email', 'anon')}"
        )
        response["X-Request-ID"] = request_id
        return response

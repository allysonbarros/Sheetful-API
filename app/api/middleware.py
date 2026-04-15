"""
Request logging middleware (spec 0010).

Emits one line per request with method, path, status, and elapsed ms, all
tagged with a request_id that is also mirrored to the ``x-request-id``
response header and into ``request.state.request_id`` so the error handler
in ``app/api/errors.py`` can reuse it as ``error_id``.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("sheetful.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed id=%s method=%s path=%s elapsed_ms=%.1f",
                request_id,
                request.method,
                request.url.path,
                elapsed,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "request id=%s method=%s path=%s status=%d elapsed_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        response.headers["x-request-id"] = request_id
        return response
